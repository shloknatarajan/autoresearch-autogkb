# AutoGKB AutoResearch Program

This document is the operating manual for an autonomous coding agent improving the
annotation system in this repo. It is modeled on Andrej Karpathy's
[`autoresearch/program.md`](https://github.com/karpathy/autoresearch/blob/master/program.md),
adapted from "minimize val_bpb on a tiny LM" to "maximize the annotation score on
`annotation_bench.jsonl`."

## Core Framework

Start each session on a fresh git branch (e.g. `autoresearch/2026-06-01`). Read these
files to orient:

- `README.md` — the task, interface, and how to run the eval.
- `src/base/model.py` — the `Annotation` data model and `AnnotationModel` interface. **Read-only.**
- `src/eval/scoring.py`, `src/eval/evaluate.py` — the scorer and harness. **Read-only.**
- `src/eval/annotation_bench.jsonl` — the benchmark / ground truth. **Read-only.**
- `results.tsv` and `logs/<attempt>/` — your own prior runs.

The **only** things you create or modify are **attempts** under `src/attempts/`.

## Operational Constraints

- **Objective:** maximize the LLM-as-judge **overall** score (the mean of the per-section
  scores) on `annotation_bench.jsonl`. Watch per-section scores to find where to improve.
- **Do not** edit the interface, scorer, harness, or benchmark. Do not change the judge
  model/prompt — scores must stay comparable across attempts.
- **Do not** weaken the eval (e.g. only evaluating easy papers and reporting it as full).
  Use `--limit` to iterate cheaply, but judge progress on full runs.
- **Exit criteria** (whichever triggers first ends the run): a target score threshold,
  a max number of attempts, or a wall-clock time budget.

## Experimentation Loop

Cycle through:

1. **Examine state** — check git, read `results.tsv`, and skim recent `logs/<attempt>/*.json`
   to see where the current best attempt loses points (which sections, which papers).
2. **Form one hypothesis** — a single, concrete change (e.g. per-table extraction,
   two-pass variant discovery, JSON-repair, better prompt for `study_parameters`).
3. **Create a new attempt** — a new folder `src/attempts/{YYYYMMDD_HHMMSS}_short_name/`:
   - `model.py` — an `AnnotationModel` subclass.
   - `__init__.py` — `from .model import YourModel` (relative import; folder names start
     with a digit and are loaded via importlib by spec).
   - `README.md` — `Created:` timestamp, an overview of the strategy and how it differs
     from prior attempts, and the `module:Class` model spec.
4. **Commit** the new attempt.
5. **Run the eval:**
   ```bash
   uv run python -m src.eval.evaluate \
       --model src.attempts.{YYYYMMDD_HHMMSS}_short_name:YourModel \
       --limit 3            # cheap smoke run first, then drop --limit for the full set
   ```
   The harness writes the full report to `logs/<attempt>/<run>.json` and appends a summary
   row to `results.tsv`.
6. **Record** the observed scores and what you learned in the attempt's `README.md`.
7. **Decide:** if the overall score improves, advance the branch. If it is equal or worse,
   `git reset` back to the starting point and keep the attempt folder only if its lesson
   is worth retaining.

## Guiding Principles

All else being equal, **simpler is better**. A marginal +0.001 overall that costs twenty
lines of inelegant code is not worth it; the same score reached by simplification is.

## Autonomous Directive

Once experimentation begins, **do NOT pause to ask the human whether to continue.** Keep
iterating through the loop until an exit criterion is met.
