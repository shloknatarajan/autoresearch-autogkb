"""Exit-criteria loop controller for the autoresearch loop.

This does NOT generate attempts — the agent (see ``program.md``) writes attempts
and runs the eval. This controller only enforces *when to stop*: it tracks the
start time and reads ``results.tsv`` to know how many iterations have run and the
best overall score so far, then decides CONTINUE or STOP against the configured
exit criteria.

Typical use (a shell loop the agent drives):

    uv run python -m src.autoresearch.loop start \
        --max-iterations 20 --time-budget 2h --target-score 0.8
    while uv run python -m src.autoresearch.loop check; do
        # ... agent creates a new attempt and runs the eval (appends results.tsv) ...
    done
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_TSV = ROOT / "results.tsv"
DEFAULT_STATE = ROOT / "logs" / "loop_state.json"

# Exit code returned by `check` when a stop criterion has tripped (so a shell
# `while` loop terminates). 0 means continue.
STOP_EXIT_CODE = 3


@dataclass
class ExitCriteria:
    max_iterations: int | None = None
    time_budget_seconds: float | None = None
    target_score: float | None = None


@dataclass
class LoopState:
    iterations: int
    best_score: float
    elapsed_seconds: float


@dataclass
class Decision:
    should_continue: bool
    reason: str


def parse_duration(text: str) -> float:
    """Parse a duration like ``90s``, ``30m``, ``2h`` (bare number = seconds)."""
    text = text.strip().lower()
    units = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    if text and text[-1] in units:
        return float(text[:-1]) * units[text[-1]]
    return float(text)


def read_ledger(path) -> tuple[int, float]:
    """Return ``(iterations, best_overall)`` from a results.tsv ledger.

    Iterations = number of data rows; best_overall = max of the ``overall``
    column. A missing or header-only file yields ``(0, 0.0)``.
    """
    path = Path(path)
    if not path.exists():
        return 0, 0.0
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    data_rows = lines[1:]  # drop header
    if not data_rows:
        return 0, 0.0
    best = max(float(row.split("\t")[3]) for row in data_rows)
    return len(data_rows), best


def decide(criteria: ExitCriteria, state: LoopState) -> Decision:
    """Pure exit decision. Target score wins (success), then iterations, then time."""
    if criteria.target_score is not None and state.best_score >= criteria.target_score:
        return Decision(
            False,
            f"target score reached: {state.best_score:.4f} >= {criteria.target_score}",
        )
    if (
        criteria.max_iterations is not None
        and state.iterations >= criteria.max_iterations
    ):
        return Decision(
            False,
            f"max iterations reached: {state.iterations} >= {criteria.max_iterations}",
        )
    if (
        criteria.time_budget_seconds is not None
        and state.elapsed_seconds >= criteria.time_budget_seconds
    ):
        return Decision(
            False,
            f"time budget exhausted: {state.elapsed_seconds:.0f}s >= {criteria.time_budget_seconds:.0f}s",
        )
    return Decision(True, "continue")


@dataclass
class LoopController:
    state_path: Path
    results_path: Path

    def start(self, criteria: ExitCriteria, now: float) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"start_epoch": now, "criteria": asdict(criteria)}, indent=2)
        )

    def _load(self) -> tuple[float, ExitCriteria]:
        data = json.loads(Path(self.state_path).read_text())
        return data["start_epoch"], ExitCriteria(**data["criteria"])

    def check(self, now: float) -> Decision:
        start_epoch, criteria = self._load()
        iterations, best = read_ledger(self.results_path)
        state = LoopState(
            iterations=iterations, best_score=best, elapsed_seconds=now - start_epoch
        )
        return decide(criteria, state)

    def status(self, now: float) -> LoopState:
        start_epoch, _ = self._load()
        iterations, best = read_ledger(self.results_path)
        return LoopState(
            iterations=iterations, best_score=best, elapsed_seconds=now - start_epoch
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Exit-criteria controller for the autoresearch loop."
    )
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="Loop state file")
    parser.add_argument(
        "--results-tsv", default=str(DEFAULT_RESULTS_TSV), help="Results ledger to read"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Initialize a loop run with exit criteria")
    p_start.add_argument("--max-iterations", type=int, default=None)
    p_start.add_argument("--time-budget", default=None, help="e.g. 90s, 30m, 2h")
    p_start.add_argument("--target-score", type=float, default=None)

    sub.add_parser(
        "check", help="Print CONTINUE/STOP; exit 0 to continue, nonzero to stop"
    )
    sub.add_parser("status", help="Print current iterations / best score / elapsed")

    args = parser.parse_args(argv)
    ctrl = LoopController(
        state_path=Path(args.state), results_path=Path(args.results_tsv)
    )
    now = time.time()

    if args.command == "start":
        criteria = ExitCriteria(
            max_iterations=args.max_iterations,
            time_budget_seconds=parse_duration(args.time_budget)
            if args.time_budget
            else None,
            target_score=args.target_score,
        )
        ctrl.start(criteria, now=now)
        print(f"Loop started. Criteria: {criteria}")
        return 0

    if args.command == "status":
        s = ctrl.status(now=now)
        print(
            f"iterations={s.iterations} best_score={s.best_score:.4f} elapsed={s.elapsed_seconds:.0f}s"
        )
        return 0

    # check
    decision = ctrl.check(now=now)
    label = "CONTINUE" if decision.should_continue else "STOP"
    print(f"{label}: {decision.reason}")
    return 0 if decision.should_continue else STOP_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
