# attempts

Each attempt is an `AnnotationModel` implementation that the eval harness can load and
score against `annotation_bench.jsonl`. See [`program.md`](../../program.md) for the
autoresearch loop these attempts are produced by.

## Convention

**Every attempt lives in its own timestamped folder**, named
`{YYYYMMDD_HHMMSS}_descriptive_attempt_name`:

```
src/attempts/20260601_204044_baseline/
├── __init__.py     # `from .model import MyModel`  (relative import — required, see note)
├── model.py        # the AnnotationModel subclass
└── README.md       # overview + creation timestamp (see below)
```

The timestamp prefix keeps attempts ordered by creation. Generate it with
`date -u +"%Y%m%d_%H%M%S"`.

> **Note:** because the folder name starts with a digit it is not a valid Python
> identifier, so `__init__.py` must use a **relative** import (`from .model import ...`),
> and attempts are loaded by spec via `importlib` (the harness does this) — never with a
> plain `import` statement.

Each attempt's `README.md` must include:

- **Created:** an ISO-8601 UTC timestamp (`date -u +"%Y-%m-%dT%H:%M:%SZ"`).
- **Overview:** what the strategy is and how it differs from prior attempts.
- **Model spec:** the `module.path:ClassName` string to pass to `--model`.
- **Results:** scores observed (the harness writes them to `logs/<attempt>/` and
  `results.tsv`).

Loaded by the harness via its spec, e.g.:

```bash
uv run python -m src.eval.evaluate --model src.attempts.20260601_204044_baseline:BaselineModel
```

Each run writes a full JSON report to `logs/<attempt>/<run-timestamp>.json` and appends a
one-line summary to the top-level `results.tsv` ledger.

## Shared tools

Attempts may import shared helpers from [`src/tools/`](../tools/) (a normal package, so
`from src.tools.<module> import ...` works). When logic is reusable beyond a single
attempt — variant normalization, table extraction, JSON repair — put it in `src/tools/`
so future attempts can reuse it rather than re-deriving it.

## Attempts

- [`20260601_204044_baseline`](20260601_204044_baseline/) — one-shot whole-paper →
  whole-annotation LLM call.
