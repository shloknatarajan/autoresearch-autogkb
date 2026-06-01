"""Tests for the evaluation harness (model loading, benchmark loading, aggregation)."""

import json

from src.base.model import Annotation, AnnotationModel
from src.eval.scoring import SECTIONS, AnnotationScore, SectionScore
from src.eval.evaluate import load_model, load_benchmark, aggregate, evaluate


class DummyModel(AnnotationModel):
    """Used by test_load_model_instantiates_from_spec via its import path."""

    def predict(self, markdown_content):
        return Annotation(variants=["rs1"], summary="dummy")


def test_load_model_instantiates_from_module_colon_class_spec():
    model = load_model("tests.test_evaluate:DummyModel")
    assert isinstance(model, DummyModel)


def test_load_benchmark_parses_records(tmp_path):
    record = {
        "pmcid": "PMC1",
        "markdown_content": "# paper",
        "annotations": {"variants": ["rs1"], "summary": "s", "title": "t"},
    }
    path = tmp_path / "bench.jsonl"
    path.write_text(json.dumps(record) + "\n")

    records = load_benchmark(path)
    assert len(records) == 1
    assert records[0].pmcid == "PMC1"
    assert records[0].markdown_content == "# paper"
    assert isinstance(records[0].ground_truth, Annotation)
    assert records[0].ground_truth.variants == ["rs1"]


def _score(per_section):
    """Build an AnnotationScore where every section gets the same value."""
    sections = {name: SectionScore(name, per_section) for name in SECTIONS}
    return AnnotationScore(sections=sections, overall=per_section)


def test_aggregate_means_overall_and_each_section():
    agg = aggregate([_score(1.0), _score(0.0)])
    assert agg.n == 2
    assert agg.overall == 0.5
    assert all(mean == 0.5 for mean in agg.sections.values())


def test_evaluate_runs_model_over_each_record_and_aggregates(tmp_path):
    record = {
        "pmcid": "PMC1",
        "markdown_content": "# paper",
        "annotations": {"variants": ["rs1"], "summary": "s"},
    }
    path = tmp_path / "bench.jsonl"
    path.write_text(json.dumps(record) + "\n")
    benchmark = load_benchmark(path)

    perfect_judge = lambda name, pred, gt: SectionScore(name, 1.0)
    per_paper, agg = evaluate(DummyModel(), benchmark, perfect_judge)

    assert len(per_paper) == 1
    assert per_paper[0][0] == "PMC1"  # (pmcid, AnnotationScore)
    assert agg.overall == 1.0
