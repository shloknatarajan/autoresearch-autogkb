# baseline

**Created:** 2026-06-01T20:40:44Z

## Overview

The starting-point attempt. Makes a **single LLM call** (via `litellm`) with the full
paper markdown and a description of the target annotation schema, then parses the
returned JSON into an `Annotation`.

- **Model spec:** `src.attempts.20260601_204044_baseline:BaselineModel`
- **Strategy:** one-shot, whole-paper → whole-annotation. No retrieval, no per-table
  specialization, no validation/repair of the output.
- **Known weaknesses:** long papers may exceed useful context; the model must produce all
  sections at once; malformed JSON fails hard.

## Run

```bash
uv run python -m src.eval.evaluate \
    --model src.attempts.20260601_204044_baseline:BaselineModel \
    --judge-model anthropic/claude-sonnet-4-5 \
    --limit 3
```

## Results

_Record scores here as you run them (see `logs/`)._
