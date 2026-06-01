"""Evaluation harness: run an AnnotationModel over the benchmark and score it.

Usage:
    uv run python -m src.eval.evaluate \
        --model src.attempts.baseline:BaselineModel \
        --judge-model anthropic/claude-sonnet-4-5

Loads ``annotation_bench.jsonl``, runs the model's ``predict`` on each paper's
markdown, scores the prediction against ground truth with an LLM-as-judge (per
section), aggregates, and writes a JSON report to ``logs/``.
"""

import argparse
import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.base.model import Annotation, AnnotationModel
from src.eval.scoring import (
    SECTIONS,
    AnnotationScore,
    Judge,
    LiteLLMJudge,
    score_annotation,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = ROOT / "src" / "eval" / "annotation_bench.jsonl"
DEFAULT_LOG_DIR = ROOT / "logs"
DEFAULT_RESULTS_TSV = ROOT / "results.tsv"

# results.tsv columns: run metadata + one score column per section.
RESULTS_HEADER = "\t".join(["timestamp", "attempt", "n", "overall", *SECTIONS])


@dataclass
class BenchmarkRecord:
    pmcid: str
    markdown_content: str
    ground_truth: Annotation


@dataclass
class AggregateScore:
    sections: dict[str, float]
    overall: float
    n: int


def load_model(spec: str) -> AnnotationModel:
    """Instantiate an AnnotationModel from a ``module.path:ClassName`` spec."""
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise ValueError(f"Model spec must be 'module.path:ClassName', got: {spec!r}")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def load_benchmark(path) -> list[BenchmarkRecord]:
    """Load benchmark records from a jsonl file."""
    records: list[BenchmarkRecord] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            records.append(
                BenchmarkRecord(
                    pmcid=row["pmcid"],
                    markdown_content=row["markdown_content"],
                    ground_truth=Annotation.from_dict(row["annotations"]),
                )
            )
    return records


def aggregate(scores: list[AnnotationScore]) -> AggregateScore:
    """Average overall and per-section scores across papers."""
    n = len(scores)
    if n == 0:
        return AggregateScore(
            sections={name: 0.0 for name in SECTIONS}, overall=0.0, n=0
        )
    section_means = {
        name: sum(s.sections[name].score for s in scores) / n for name in SECTIONS
    }
    overall = sum(s.overall for s in scores) / n
    return AggregateScore(sections=section_means, overall=overall, n=n)


def evaluate(
    model: AnnotationModel, benchmark: list[BenchmarkRecord], judge: Judge
) -> tuple[list[tuple[str, AnnotationScore]], AggregateScore]:
    """Run the model over the benchmark and score each prediction.

    Returns ``(per_paper, aggregate)`` where per_paper is a list of
    ``(pmcid, AnnotationScore)``.
    """
    per_paper: list[tuple[str, AnnotationScore]] = []
    for record in benchmark:
        prediction = model.predict(record.markdown_content)
        score = score_annotation(prediction, record.ground_truth, judge)
        per_paper.append((record.pmcid, score))
    return per_paper, aggregate([s for _, s in per_paper])


def _report(per_paper, agg: AggregateScore) -> dict:
    return {
        "aggregate": {
            "n": agg.n,
            "overall": agg.overall,
            "sections": agg.sections,
        },
        "papers": [
            {
                "pmcid": pmcid,
                "overall": score.overall,
                "sections": {
                    name: {"score": s.score, "rationale": s.rationale}
                    for name, s in score.sections.items()
                },
            }
            for pmcid, score in per_paper
        ],
    }


def attempt_name_from_spec(spec: str) -> str:
    """The attempt's folder name = the leaf module of its ``module:Class`` spec."""
    module_path = spec.split(":", 1)[0]
    return module_path.rsplit(".", 1)[-1]


def results_row(timestamp: str, attempt_name: str, agg: AggregateScore) -> str:
    """One tab-separated ledger row: metadata + per-section scores."""
    cols = [timestamp, attempt_name, str(agg.n), f"{agg.overall:.4f}"]
    cols += [f"{agg.sections[name]:.4f}" for name in SECTIONS]
    return "\t".join(cols)


def append_results_row(
    path, timestamp: str, attempt_name: str, agg: AggregateScore
) -> None:
    """Append a row to the results.tsv ledger, writing the header if it's new."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a") as f:
        if write_header:
            f.write(RESULTS_HEADER + "\n")
        f.write(results_row(timestamp, attempt_name, agg) + "\n")


def write_run_log(report: dict, attempt_name: str, timestamp: str, logs_dir) -> Path:
    """Write the full JSON run report to ``<logs_dir>/<attempt_name>/<timestamp>.json``."""
    folder = Path(logs_dir) / attempt_name
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{timestamp.replace(':', '')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return out


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Score an AnnotationModel against the benchmark."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model spec, e.g. src.attempts.<attempt>:ModelClass",
    )
    parser.add_argument(
        "--judge-model",
        default="anthropic/claude-sonnet-4-5",
        help="litellm model string for the judge",
    )
    parser.add_argument("--bench-path", default=str(DEFAULT_BENCH))
    parser.add_argument(
        "--limit", type=int, default=None, help="Only evaluate the first N papers"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override the run-log path (default: logs/<attempt>/<run>.json)",
    )
    parser.add_argument(
        "--results-tsv",
        default=str(DEFAULT_RESULTS_TSV),
        help="Ledger to append the run summary to",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Print scores but don't write the run log or ledger",
    )
    args = parser.parse_args(argv)

    model = load_model(args.model)
    benchmark = load_benchmark(args.bench_path)
    if args.limit is not None:
        benchmark = benchmark[: args.limit]
    judge = LiteLLMJudge(model=args.judge_model)

    per_paper, agg = evaluate(model, benchmark, judge)
    report = _report(per_paper, agg)

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = attempt_name_from_spec(args.model)

    print(f"Evaluated {agg.n} papers. Overall: {agg.overall:.3f}")
    for name in SECTIONS:
        print(f"  {name:18s} {agg.sections[name]:.3f}")

    if not args.no_log:
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            out_path = write_run_log(report, attempt, run_ts, DEFAULT_LOG_DIR)
        append_results_row(args.results_tsv, run_ts, attempt, agg)
        print(f"Run log:    {out_path}")
        print(f"Ledger:     {args.results_tsv}")


if __name__ == "__main__":
    main()
