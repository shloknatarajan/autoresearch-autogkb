"""Tests for the exit-criteria loop controller."""

import pytest

from src.autoresearch.loop import (
    ExitCriteria,
    LoopState,
    Decision,
    parse_duration,
    read_ledger,
    decide,
    LoopController,
)


# --- parse_duration ---------------------------------------------------------


@pytest.mark.parametrize(
    "text,seconds",
    [("90s", 90.0), ("30m", 1800.0), ("2h", 7200.0), ("45", 45.0), ("1.5h", 5400.0)],
)
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


# --- read_ledger ------------------------------------------------------------


def test_read_ledger_counts_rows_and_finds_best_overall(tmp_path):
    path = tmp_path / "results.tsv"
    path.write_text(
        "timestamp\tattempt\tn\toverall\tvariants\n"
        "t1\ta1\t3\t0.4000\t0.5\n"
        "t2\ta2\t3\t0.7000\t0.6\n"
        "t3\ta3\t3\t0.6000\t0.6\n"
    )
    iterations, best = read_ledger(path)
    assert iterations == 3
    assert best == 0.7


def test_read_ledger_handles_missing_or_header_only(tmp_path):
    assert read_ledger(tmp_path / "nope.tsv") == (0, 0.0)
    p = tmp_path / "h.tsv"
    p.write_text("timestamp\tattempt\tn\toverall\n")
    assert read_ledger(p) == (0, 0.0)


# --- decide (pure) ----------------------------------------------------------


def test_decide_continues_when_no_criterion_met():
    c = ExitCriteria(max_iterations=10, time_budget_seconds=3600, target_score=0.9)
    d = decide(c, LoopState(iterations=2, best_score=0.5, elapsed_seconds=100))
    assert d.should_continue is True


def test_decide_stops_on_target_score_first():
    c = ExitCriteria(max_iterations=10, time_budget_seconds=3600, target_score=0.8)
    d = decide(c, LoopState(iterations=2, best_score=0.85, elapsed_seconds=100))
    assert d.should_continue is False
    assert "target" in d.reason.lower()


def test_decide_stops_on_max_iterations():
    c = ExitCriteria(max_iterations=5)
    d = decide(c, LoopState(iterations=5, best_score=0.1, elapsed_seconds=0))
    assert d.should_continue is False
    assert "iteration" in d.reason.lower()


def test_decide_stops_on_time_budget():
    c = ExitCriteria(time_budget_seconds=60)
    d = decide(c, LoopState(iterations=1, best_score=0.1, elapsed_seconds=61))
    assert d.should_continue is False
    assert "time" in d.reason.lower()


def test_decide_continues_when_all_criteria_none():
    d = decide(
        ExitCriteria(), LoopState(iterations=99, best_score=1.0, elapsed_seconds=1e9)
    )
    assert d.should_continue is True


# --- LoopController (start/check roundtrip with injected clock) -------------


def test_controller_start_then_check_uses_elapsed_and_ledger(tmp_path):
    results = tmp_path / "results.tsv"
    results.write_text("timestamp\tattempt\tn\toverall\nt1\ta1\t3\t0.3000\n")
    state = tmp_path / "loop_state.json"

    ctrl = LoopController(state_path=state, results_path=results)
    ctrl.start(ExitCriteria(max_iterations=5, time_budget_seconds=100), now=1000.0)

    cont = ctrl.check(now=1050.0)  # 50s elapsed, 1 iteration, best 0.3
    assert cont.should_continue is True

    stop = ctrl.check(now=1101.0)  # 101s elapsed > 100s budget
    assert stop.should_continue is False
    assert "time" in stop.reason.lower()
