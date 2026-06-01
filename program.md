# AutoGKB AutoResearch Program

Give an AI agent a small but real annotation task and let it experiment autonomously: the
agent writes an annotation model, scores it against the benchmark, keeps what helps,
reverts what doesn't, and repeats. This file is the agent's instruction set, modeled on
Andrej Karpathy's [`autoresearch/program.md`](https://github.com/karpathy/autoresearch/blob/master/program.md)
(adapted from "minimize val_bpb" to "maximize the annotation score").

## Core Setup Process

1. **Agree on a tag.** Propose a short date-based tag (e.g. `jun1`) and confirm the branch
   `autoresearch/<tag>` does not already exist.
2. **Create the branch:** `git checkout -b autoresearch/<tag>` from `main`.
3. **Read the context:** `README.md`, `src/base/model.py` (the interface, **read-only**),
   `src/eval/scoring.py` and `src/eval/evaluate.py` (the scorer/harness, **read-only**),
   `src/attempts/README.md` (the attempt convention), and `src/tools/README.md` (the
   shared tool library).
4. **Verify the setup:** `uv sync` then `uv run pytest -q` (all green).
5. **Confirm** the benchmark is present: `src/eval/annotation_bench.jsonl` (32 papers).
6. The results ledger `results.tsv` is created automatically on the first eval run.

## Experimental Constraints

- **Modifiable:** **attempts** (new folders under `src/attempts/`) and **shared tools**
  (`src/tools/` — a cross-run library attempts import from; add reusable helpers here so
  future attempts benefit, see `src/tools/README.md`). Everything else (the `Annotation`
  interface, the scorer, the harness, the benchmark, the judge model/prompt) is **fixed**
  so scores stay comparable across attempts.
- **No weakening the eval:** use `--limit` to iterate cheaply, but judge real progress on
  full runs. Do not change the judge.
- **Success metric:** maximize the LLM-as-judge **overall** score (mean of the per-section
  scores) on `annotation_bench.jsonl`. Watch per-section scores to find where to improve.
- **Budget / exit criteria** (whichever trips first): a target overall score, a max number
  of attempts, or a wall-clock budget — enforced by `src/autoresearch/loop.py` (optional;
  see below). Otherwise, run until the human interrupts.
- **Simpler is better.** A marginal +0.001 overall that costs twenty lines of inelegant
  code is not worth it; the same score reached by simplification is.

## Results Tracking

Every eval run appends one row to `results.tsv` (tracked in git, so run history is kept):

```
timestamp · attempt · n · overall · variants · summary · study_parameters · var_drug_ann · var_pheno_ann · var_fa_ann
```

and writes a full report to `logs/<attempt>/<run>.json`. In each attempt's `README.md`,
record the outcome and a one-word status: **keep** (improved overall, advance the branch),
**discard** (equal/worse, revert), or **crash** (the run failed).

## Autonomous Loop

Execute until an exit criterion trips (or the human interrupts):

1. Review git state, `results.tsv`, and recent `logs/<attempt>/*.json` to see where the
   current best attempt loses points (which sections, which papers).
2. Form **one** hypothesis and create a new attempt folder
   `src/attempts/{YYYYMMDD_HHMMSS}_short_name/` (`model.py` + `__init__.py` with a relative
   import + `README.md` with a `Created:` timestamp). See `src/attempts/README.md`. Import
   shared helpers from `src/tools/`, and move any logic worth reusing into `src/tools/`.
3. Commit the new attempt.
4. Run the eval:
   ```bash
   uv run python -m src.eval.evaluate \
       --model src.attempts.{YYYYMMDD_HHMMSS}_short_name:YourModel --limit 3
   ```
   then drop `--limit` for a full run once it looks promising.
5. Read the scores from the run log; note them in the attempt's README.
6. **If overall improves, advance the branch. If equal or worse, `git reset` back** to the
   prior state.

Optionally gate the loop on explicit exit criteria:

```bash
uv run python -m src.autoresearch.loop start --max-iterations 20 --time-budget 2h --target-score 0.8
while uv run python -m src.autoresearch.loop check; do
    #  ... one iteration of the loop above ...
done
```

## Autonomous Directive

Once experimentation begins, **do NOT pause to ask the human whether to continue.** The
loop runs until an exit criterion trips or the human interrupts you, period.
