"""Resolve hand-written grounding questions to exact edition/document IDs and report coverage."""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from rule_u.ingestion import save_json  # noqa: E402
from rule_u.stage5 import text_quality  # noqa: E402

data = ROOT / "data"
sources = {}
for path in sorted((data / "manifests").glob("*.json")):
    for source in json.loads(path.read_text(encoding="utf-8")):
        if source["status"] == "extracted":
            artifact = json.loads((data / source["extracted_key"]).read_text(encoding="utf-8"))
            sources[source["edition_id"]] = {**source, "page_count": len(artifact["pages"]),
                                             "quality": text_quality(artifact["pages"])["status"]}

parser = argparse.ArgumentParser()
parser.add_argument("--questions", default="evals/stage5-grounding-questions.tsv")
parser.add_argument("--output", default="evals/stage5-grounding-cases.json")
parser.add_argument("--origin", default="stage5_grounding")
parser.add_argument("--no-smoke", action="store_true", help="omit the stage 2 smoke cases")
args = parser.parse_args()
cases = [] if args.no_smoke else json.loads(
    (ROOT / "evals/retrieval-smoke-cases.json").read_text(encoding="utf-8"))
for case in cases:
    case["origin"] = "stage2_smoke"
with (ROOT / args.questions).open(encoding="utf-8", newline="") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        matches = [s for e, s in sources.items()
                   if s["game_id"] == row["game_id"] and e.startswith(row["edition_prefix"])]
        if len(matches) != 1:
            raise SystemExit(f"edition prefix not unique: {row}")
        # Extra pages are added only where the same rule is stated again (label review).
        source, pages = matches[0], [int(x) for x in row["pages"].split(",")]
        if not all(1 <= p <= source["page_count"] for p in pages) or source["quality"] != "readable":
            raise SystemExit(f"invalid page or unreadable source: {row}")
        cases.append({"game_id": row["game_id"], "edition_id": source["edition_id"],
                      "document_id": source["document_id"], "question": row["question"],
                      "pages": pages, "origin": args.origin})

covered = {c["edition_id"] for c in cases}
readable = {e for e, s in sources.items() if s["quality"] == "readable"}
save_json(ROOT / args.output, cases)
print(json.dumps({"cases": len(cases), "games": len({c["game_id"] for c in cases}),
                  "readable_editions": len(readable),
                  "uncovered_readable_editions": sorted(readable - covered)}, ensure_ascii=False))
