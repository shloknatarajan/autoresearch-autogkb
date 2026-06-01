# AutoGKB AutoResearch Pipeline

A Karpathy-style *autoresearch* repo. The goal is to let a CLI coding agent (e.g. Claude
Code) iteratively build and improve an LLM system that, given a pharmacogenomics paper's
markdown, **reproduces the structured curation** a human team produced — variants, a
summary, study parameters, and the variant-drug / variant-phenotype / variant-functional
annotation tables.

The target is the human-curated benchmark in
[`src/eval/annotation_bench.jsonl`](src/eval/annotation_bench.jsonl).

---

## Goal

Given **only** a paper's markdown content, produce a structured `Annotation` object that
mirrors the original PharmGKB-style curation:

```
markdown (one paper)  ──▶  {
    "variants": ["rs9923231", "rs1057910", ...],
    "title": "...",
    "summary": "...",
    "study_parameters": [ {...}, ... ],
    "var_drug_ann":     [ {...}, ... ],
    "var_pheno_ann":    [ {...}, ... ],
    "var_fa_ann":       [ {...}, ... ]
}
```

The system reproduces the **entire** annotations object. It must discover the variants
and associations itself from the text — it is not handed any of them.

---

## Repository layout

| Path | What it is |
| --- | --- |
| `articles/` | 3,066 paper markdowns (`PMC<id>.md`). The model's input. |
| `annotations/` | 33 raw human-curated annotation JSONs (`PMC<id>.json`). Source material for the benchmark and useful as reference. |
| `src/base/model.py` | The `Annotation` data model and the `AnnotationModel` interface every attempt inherits. |
| `src/attempts/` | `AnnotationModel` implementations — one timestamped folder per attempt (see `src/attempts/README.md`). `20260601_204044_baseline/` is the starting point. |
| `src/tools/` | Shared, cross-run tool library attempts import from and extend (see `src/tools/README.md`). Editable; persists across attempts/branches. |
| `src/eval/annotation_bench.jsonl` | The benchmark: 32 papers, each with `pmcid`, `pmid`, `variants`, `annotations` (ground truth), and `markdown_content`. |
| `src/eval/scoring.py` | Per-section LLM-as-judge scoring (judge-injected, so the aggregation is unit-tested). |
| `src/eval/evaluate.py` | The evaluation harness + CLI. |
| `src/autoresearch/loop.py` | Exit-criteria controller — enforces when the loop stops (max iterations / time budget / target score). |
| `program.md` | The autonomous operating manual for the autoresearch agent (loop, constraints, exit criteria). |
| `results.tsv` | Append-only ledger: one summary row (overall + per-section) per eval run. Tracked, so run history is kept in git. |
| `tests/` | Pytest suite for the interface, scoring, harness, and baseline. |
| `logs/<attempt>/` | Full JSON run reports, one file per eval run, grouped by attempt. Tracked. |

`src/eval/` also carries legacy sentence-level benchmark data
(`sentence_bench*.jsonl`) the annotation benchmark was originally derived from; it is not
used by the active pipeline.

---

## Task definition

- **Input:** the markdown string for a single paper (`markdown_content` in a benchmark
  record, or any file in `articles/`).
- **Output:** an `Annotation` reproducing the full curation for that paper.
- The 32 benchmark papers also have markdown and raw annotations available; **nothing is
  held out**, so be mindful of overfitting/memorization when reading scores.

### Annotation shape

The `annotations` object (and the `Annotation` data model) has these sections:

| Section | Type | Meaning |
| --- | --- | --- |
| `variants` | `list[str]` | Variant identifiers discussed (rsIDs / variant strings). |
| `title` | `str` | Paper title. |
| `summary` | `str` | Free-text summary of the pharmacogenomic findings. |
| `study_parameters` | `list[dict]` | Study-level metadata (study type, cases/controls, p-values, ...). |
| `var_drug_ann` | `list[dict]` | Variant↔drug association records. |
| `var_pheno_ann` | `list[dict]` | Variant↔phenotype association records. |
| `var_fa_ann` | `list[dict]` | Variant functional-assay association records. |

The table rows keep the curated field names verbatim (e.g. `"Drug(s)"`,
`"Is/Is Not associated"`), so they are represented as plain dicts rather than typed
fields.

---

## Model interface

Every attempt subclasses one interface so the harness can swap implementations and score
them uniformly:

```python
# src/base/model.py
@dataclass
class Annotation:
    variants: list[str]
    title: str
    summary: str
    study_parameters: list[dict]
    var_drug_ann: list[dict]
    var_pheno_ann: list[dict]
    var_fa_ann: list[dict]
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Annotation": ...   # ignores unmodeled keys

class AnnotationModel(ABC):
    @abstractmethod
    def predict(self, markdown_content: str) -> Annotation: ...
```

A new attempt = a new `AnnotationModel` subclass in its own folder under
`src/attempts/` (one folder per attempt, each with a README + creation timestamp — see
[`src/attempts/README.md`](src/attempts/README.md)). See
[`src/attempts/20260601_204044_baseline/`](src/attempts/20260601_204044_baseline/) for a
one-shot LLM example.

---

## Evaluation

Run with:

```bash
uv run python -m src.eval.evaluate \
    --model src.attempts.20260601_204044_baseline:BaselineModel \
    --judge-model anthropic/claude-sonnet-4-5
```

Scoring is **pure LLM-as-judge**, run **per section** so the results are interpretable.
For each of `variants`, `summary`, `study_parameters`, `var_drug_ann`, `var_pheno_ann`,
and `var_fa_ann`, the judge compares the predicted value against ground truth and returns
a score in `[0, 1]` (rewarding recall of the curated content, penalizing spurious or
incorrect content). The harness reports **per-section scores plus a mean overall**, both
per paper and aggregated. Each run writes a full JSON report to
`logs/<attempt>/<run-timestamp>.json` and appends a one-line summary (overall +
per-section) to the `results.tsv` ledger. Use `--no-log` to skip both.

All LLM calls — the judge and the models — go through
[`litellm`](https://docs.litellm.ai/), so any provider can be used by changing the model
string (set the matching `*_API_KEY` env var). The judge model/prompt is held fixed
across attempts for comparability.

Useful flags: `--limit N` (only the first N papers — handy while iterating),
`--bench-path`, `--results-tsv`, `--output`, `--no-log`.

---

## AutoResearch loop

This is the Karpathy-style part: give an agent the task and let it experiment
autonomously. **The loop is the agent itself** — there is no driver script. You launch it
by pointing a coding agent at [`program.md`](program.md), which is its complete operating
manual.

### Launching autonomous research

Spin up your coding agent (Claude Code, Codex, etc.) in this repo, relax its permissions
so it can run commands unattended, then prompt something like:

> "Have a look at `program.md` and let's kick off a new experiment — do the setup first."

The agent then loops on its own (because `program.md` tells it to, and not to pause for
approval): read state → form one hypothesis → write a new attempt under `src/attempts/` →
commit → run the eval → keep if the overall score improved, else `git reset`. Each run
appends to `results.tsv` and writes `logs/<attempt>/<run>.json`.

### Optional: enforce exit criteria

`program.md` says to run until the human interrupts. To bound a run instead, gate it on
the controller in `src/autoresearch/loop.py` (whichever triggers first stops it):

- **Score threshold** — best overall score reaches a goal (`--target-score`).
- **Max iterations** — N runs recorded in `results.tsv` (`--max-iterations`).
- **Time budget** — a wall-clock budget (`--time-budget`, e.g. `2h`).

```bash
uv run python -m src.autoresearch.loop start --max-iterations 20 --time-budget 2h --target-score 0.8
while uv run python -m src.autoresearch.loop check; do
    # one iteration: agent creates a new attempt + runs the eval (appends to results.tsv)
done
```

The controller tracks start time and reads `results.tsv`; it does **not** create attempts.

---

## Getting started

This project uses [`uv`](https://docs.astral.sh/uv/) (Python ≥ 3.12).

```bash
# install deps (incl. pytest, litellm)
uv sync

# run the test suite
uv run pytest -q

# evaluate the baseline on a few papers
export ANTHROPIC_API_KEY=...        # or the key for whatever --judge-model you pick
uv run python -m src.eval.evaluate \
    --model src.attempts.20260601_204044_baseline:BaselineModel --limit 3
```

---

## Status / TODO

- [x] `Annotation` + `AnnotationModel` interface (`src/base/model.py`).
- [x] Per-section LLM-as-judge scoring (`src/eval/scoring.py`).
- [x] Evaluation harness + CLI (`src/eval/evaluate.py`).
- [x] One-shot baseline attempt (`src/attempts/20260601_204044_baseline/`).
- [x] Per-run logging (`logs/<attempt>/<run>.json`) + `results.tsv` ledger.
- [x] Autoresearch operating manual (`program.md`).
- [x] Exit-criteria loop controller (`src/autoresearch/loop.py`).
- [ ] Stronger attempts (per-table extraction, multi-pass, validation against the schema).
