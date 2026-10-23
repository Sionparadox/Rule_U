"""Compare follow-up search queries: legacy (all recent user turns joined) vs rewritten.

Live use sends the questions to the embedding API and, for follow-ups, the conversation text
(no rulebook text) to the chat API for rewriting. Writes data/followup-evaluation.json.
"""
import argparse
import asyncio
import json

from rule_u.config import ROOT, Settings
from rule_u.ingestion import save_json, vector_collections
from rule_u.providers import chat_provider
from rule_u.rag import search_query
from rule_u.search import search
from rule_u.stage5 import query_vector

MODES = ("similarity", "hybrid")


def resolve(settings, case):
    for path in (settings.data_dir / "manifests").glob(f"{case['game_id']}.json"):
        for source in json.loads(path.read_text(encoding="utf-8")):
            if source["status"] == "extracted" and source["edition_id"].startswith(case["edition_prefix"]):
                return source
    raise ValueError("unknown_edition: " + case["id"])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--output", default="followup-evaluation.json")
    args = parser.parse_args()
    settings = Settings()
    cases = json.loads((ROOT / "evals/followup-questions.json").read_text(encoding="utf-8"))
    fingerprint, collections = vector_collections(settings)
    rows = []
    for case in cases:
        source = resolve(settings, case)
        messages = []
        for turn in case["turns"]:
            messages += [{"role": "user", "content": turn}, {"role": "assistant", "content": "(앞 답변)"}]
        messages = messages[:-1]
        legacy = "\n".join(m["content"] for m in messages[-6:] if m["role"] == "user")
        rewritten, detail = await search_query(settings, {"messages": messages},
                                               lambda: chat_provider(settings))
        where = {"$and": [{"game_id": case["game_id"]}, {"edition_id": source["edition_id"]}]}
        row = {**case, "edition_id": source["edition_id"], "query_method": detail["query_method"],
               "queries": {"legacy": legacy, "new": rewritten}, "ranks": {}}
        for variant, text in row["queries"].items():
            vector, _ = await query_vector(settings, fingerprint, text)
            for mode in MODES:
                found = search(collections["rule_docs"], vector, text, where, mode, 5,
                               settings.candidate_k)[:5]
                ranks = [i + 1 for i, (m, _) in enumerate(found)
                         if m["document_id"] == source["document_id"] and m["page_start"] in case["pages"]]
                row["ranks"][f"{variant}/{mode}"] = ranks[0] if ranks else None
        rows.append(row)
        print(json.dumps({"id": case["id"], "method": detail["query_method"], "ranks": row["ranks"]}),
              flush=True)
    summary = {}
    for kind in ("followup", "switch", "all"):
        subset = [r for r in rows if kind == "all" or r["kind"] == kind]
        summary[kind] = {key: {"hit_at_5": sum(r["ranks"][key] is not None for r in subset) / len(subset),
                               "mrr_at_5": sum(1 / r["ranks"][key] for r in subset if r["ranks"][key])
                               / len(subset)}
                         for key in rows[0]["ranks"]}
    save_json(settings.data_dir / args.output, {"fingerprint": fingerprint, "count": len(rows),
                                                "summary": summary, "cases": rows})


if __name__ == "__main__":
    asyncio.run(main())
