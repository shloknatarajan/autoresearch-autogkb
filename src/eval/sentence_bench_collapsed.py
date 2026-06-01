"""Build sentence_bench_collapsed.jsonl from sentence_bench.jsonl.

Same content as sentence_bench.jsonl but collapsed to one line per PMCID: the
per-variant rows are merged, keeping a `variants` list and the union of their
`sentences`.
"""

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENTENCE_BENCH = ROOT / "src" / "eval" / "sentence_bench.jsonl"
COLLAPSED = ROOT / "src" / "eval" / "sentence_bench_collapsed.jsonl"


def main() -> None:
    # Preserve first-seen PMCID order from sentence_bench.jsonl.
    grouped: "OrderedDict[str, list]" = OrderedDict()
    with SENTENCE_BENCH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            grouped.setdefault(row["pmcid"], []).append(row)

    written = 0
    with COLLAPSED.open("w") as out:
        for pmcid, rows in grouped.items():
            sentences: list = []
            for r in rows:
                for s in r["sentences"]:
                    if s not in sentences:
                        sentences.append(s)

            record = {
                "pmcid": pmcid,
                "pmid": rows[0]["pmid"],
                "variants": [r["variant"] for r in rows],
                "sentences": sentences,
                "markdown_content": rows[0]["markdown_content"],
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"Wrote {written} records to {COLLAPSED}")


if __name__ == "__main__":
    main()
