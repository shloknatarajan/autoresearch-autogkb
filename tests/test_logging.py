"""Tests for run-log saving and the results.tsv ledger."""

import json

from src.eval.evaluate import (
    AggregateScore,
    attempt_name_from_spec,
    results_row,
    RESULTS_HEADER,
    append_results_row,
    write_run_log,
)
from src.eval.scoring import SECTIONS


def _agg(overall=0.5):
    return AggregateScore(
        sections={name: overall for name in SECTIONS}, overall=overall, n=3
    )


def test_attempt_name_is_leaf_module_of_spec():
    assert (
        attempt_name_from_spec("src.attempts.20260601_204044_baseline:BaselineModel")
        == "20260601_204044_baseline"
    )
    assert attempt_name_from_spec("tests.test_evaluate:DummyModel") == "test_evaluate"


def test_results_row_is_tab_separated_with_all_columns():
    row = results_row("2026-06-01T20:40:44Z", "20260601_204044_baseline", _agg(0.5))
    cols = row.split("\t")
    # timestamp, attempt, n, overall, + one column per section
    assert cols[0] == "2026-06-01T20:40:44Z"
    assert cols[1] == "20260601_204044_baseline"
    assert cols[2] == "3"
    assert len(cols) == 4 + len(SECTIONS)
    assert RESULTS_HEADER.split("\t")[:4] == ["timestamp", "attempt", "n", "overall"]


def test_append_results_row_writes_header_once_then_appends(tmp_path):
    path = tmp_path / "results.tsv"
    append_results_row(path, "ts1", "att", _agg(0.4))
    append_results_row(path, "ts2", "att", _agg(0.6))
    lines = path.read_text().splitlines()
    assert lines[0] == RESULTS_HEADER  # header written exactly once
    assert lines[1].startswith("ts1\t")
    assert lines[2].startswith("ts2\t")
    assert len(lines) == 3


def test_write_run_log_writes_json_under_attempt_folder(tmp_path):
    report = {"aggregate": {"overall": 0.5}, "papers": []}
    out = write_run_log(
        report, "20260601_204044_baseline", "2026-06-01T20:40:44Z", tmp_path
    )
    assert out.parent.name == "20260601_204044_baseline"
    assert json.loads(out.read_text())["aggregate"]["overall"] == 0.5
