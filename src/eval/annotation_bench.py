"""Build annotation_bench.jsonl from sentence_bench.jsonl.

Same as sentence_bench.jsonl but collapsed to one line per PMCID, with the raw
text `sentences` replaced by the entire annotation file (annotations/{PMCID}.json)
under an `annotations` key.
"""

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENTENCE_BENCH = ROOT / "src" / "eval" / "sentence_bench.jsonl"
ANNOTATION_BENCH = ROOT / "src" / "eval" / "annotation_bench.jsonl"
ANNOTATIONS_DIR = ROOT / "annotations"


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
    with ANNOTATION_BENCH.open("w") as out:
        for pmcid, rows in grouped.items():
            ann_path = ANNOTATIONS_DIR / f"{pmcid}.json"
            if not ann_path.exists():
                raise FileNotFoundError(f"Missing annotation file: {ann_path}")
            with ann_path.open() as af:
                annotations = json.load(af)

            # Fields constant per PMCID carry over from sentence_bench; the
            # per-variant rows collapse into a single `variants` list.
            record = {
                "pmcid": pmcid,
                "pmid": rows[0]["pmid"],
                "variants": [r["variant"] for r in rows],
                "annotations": annotations,
                "markdown_content": rows[0]["markdown_content"],
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"Wrote {written} records to {ANNOTATION_BENCH}")


if __name__ == "__main__":
    main()
