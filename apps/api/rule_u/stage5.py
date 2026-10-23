"""Stage 5: per-edition support audit and search-mode comparison over the same chunk set."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from sqlalchemy import select

from rule_u.config import Settings
from rule_u.db import make_engine, make_sessions
from rule_u.discovery import normalize
from rule_u.ingestion import digest, load_catalog, save_json, vector_collections
from rule_u.models import DocumentScope, Edition
from rule_u.providers import embedding_provider
from rule_u.search import search

MODES = ("similarity", "hybrid", "mmr")


def unreadable(text):
    """Broken font maps decode to Armenian/Hebrew/Arabic-range noise; tables lack words."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return True
    noise = sum(0x0370 <= ord(c) <= 0x10FF or 0x1200 <= ord(c) <= 0x1FFF
                or 0xE000 <= ord(c) <= 0xF8FF for c in chars)
    letters = sum(0xAC00 <= ord(c) <= 0xD7A3 or c.isascii() and c.isalpha() for c in chars)
    return noise / len(chars) > 0.5 or letters / len(chars) < 0.3


def text_quality(pages):
    bad = [p["page"] for p in pages if unreadable(p["text"])]
    # A few noisy illustration/other-language pages are tolerated; most pages must read.
    return {"unreadable_pages": bad, "pages": len(pages),
            "status": "garbled" if len(bad) * 2 >= len(pages) else "readable"}


async def query_vector(settings, fingerprint, question):
    path = settings.data_dir / "query-cache" / f"{digest((fingerprint + normalize(question)).encode())}.json"
    if path.exists():
        return json.loads(path.read_text()), True
    vector = (await embedding_provider(settings).embed([question]))[0]
    save_json(path, vector)
    return vector, False


async def evaluate_modes(settings, cases, modes=MODES, top_k=5):
    if not cases:
        raise ValueError("empty_evaluation_cases")
    fingerprint, collections = vector_collections(settings)
    rules = collections["rule_docs"]
    rows = []
    for case in cases:
        start = time.perf_counter()
        vector, hit = await query_vector(settings, fingerprint, case["question"])
        embed_seconds = time.perf_counter() - start
        # Cases target rulebooks; unrelated FAQ/errata stay out as in live retrieval.
        where = {"$and": [{"game_id": case["game_id"]}, {"edition_id": case["edition_id"]},
                          {"document_type": {"$nin": ["faq", "errata"]}}]}
        row = {**case, "cache_hit": hit, "embed_seconds": round(embed_seconds, 4), "modes": {}}
        for mode in modes:
            begin = time.perf_counter()
            found = search(rules, vector, case["question"], where, mode, top_k,
                           settings.candidate_k)[:top_k]
            seconds = time.perf_counter() - begin
            ranks = [i + 1 for i, (m, _) in enumerate(found)
                     if m["document_id"] == case["document_id"] and m["page_start"] in case["pages"]]
            row["modes"][mode] = {
                "rank": ranks[0] if ranks else None,
                "distinct_pages": len({(m["document_id"], m["page_start"]) for m, _ in found}),
                "search_seconds": round(seconds, 4),
                "retrieved": [{"chunk_id": m["chunk_id"], "page": m["page_start"]} for m, _ in found],
            }
        rows.append(row)
    summary = {}
    for mode in modes:
        ranks = [r["modes"][mode]["rank"] for r in rows]
        summary[mode] = {
            "hit_at_1": sum(r == 1 for r in ranks) / len(rows),
            "hit_at_3": sum(r is not None and r <= 3 for r in ranks) / len(rows),
            "hit_at_5": sum(r is not None for r in ranks) / len(rows),
            "mrr_at_5": sum(1 / r for r in ranks if r) / len(rows),
            "mean_distinct_pages": sum(r["modes"][mode]["distinct_pages"] for r in rows) / len(rows),
            "mean_search_seconds": sum(r["modes"][mode]["search_seconds"] for r in rows) / len(rows),
        }
    return {"fingerprint": fingerprint, "count": len(rows), "summary": summary, "cases": rows}


def audit(settings, rows, cases, evaluation, mode="similarity", apply=False):
    """An edition is supported only when every check passes; failures stay out of totals."""
    fingerprint, collections = vector_collections(settings)
    rules = collections["rule_docs"]
    passed = {(c["edition_id"]) for c in evaluation["cases"]
              if c["modes"][mode]["rank"] is not None}
    questioned = {c["edition_id"] for c in cases}
    engine = make_engine(settings)
    editions = []
    try:
        with make_sessions(engine).begin() as db:
            for row in rows:
                manifest = settings.data_dir / "manifests" / f"{row['slug']}.json"
                sources = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
                for item in row["editions"]:
                    reasons, documents = [], []
                    own = [s for s in sources if s["edition_id"] == item["id"]]
                    if not item.get("documents") or not own:
                        reasons.append("document_missing")
                    for source in own:
                        if source["status"] != "extracted":
                            reasons.append("extraction_failed")
                            continue
                        artifact = json.loads((settings.data_dir / source["extracted_key"])
                                              .read_text(encoding="utf-8"))
                        quality = text_quality(artifact["pages"])
                        if quality["status"] != "readable":
                            reasons.append("garbled_text")
                        scope = db.scalar(select(DocumentScope).where(
                            DocumentScope.document_id == source["document_id"],
                            DocumentScope.game_id == row["slug"],
                            DocumentScope.edition_id == item["id"]))
                        if scope is None:
                            reasons.append("edition_link_missing")
                        indexed = rules.get(where={"$and": [
                            {"document_id": source["document_id"]}, {"edition_id": item["id"]},
                            {"game_id": row["slug"]}]}, include=[])["ids"]
                        if len(indexed) != len(artifact["chunks"]):
                            reasons.append("index_incomplete")
                        documents.append({"document_id": source["document_id"],
                                          "source_type": source["source_type"],
                                          "chunks": len(artifact["chunks"]),
                                          "indexed": len(indexed), **quality})
                    if item["id"] not in questioned:
                        reasons.append("grounding_question_missing")
                    elif item["id"] not in passed:
                        reasons.append("grounding_question_failed")
                    reasons = sorted(set(reasons))
                    edition = db.get(Edition, item["id"])
                    if edition is None:
                        reasons.append("edition_not_imported")
                    elif apply:
                        edition.supported = not reasons
                    editions.append({"game_id": row["slug"], "edition_id": item["id"],
                                     "supported": not reasons, "reasons": reasons,
                                     "documents": documents})
            if not apply:
                db.rollback()
    finally:
        engine.dispose()
    games = {}
    for e in editions:
        games.setdefault(e["game_id"], []).append(e["supported"])
    return {"fingerprint": fingerprint, "mode": mode, "applied": apply,
            "games": len(games), "supported_games": sum(any(v) for v in games.values()),
            "editions": len(editions), "supported_editions": sum(e["supported"] for e in editions),
            "unsupported_games": sorted(g for g, v in games.items() if not any(v)),
            "items": editions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["compare", "audit"])
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, help="compare output reused by audit")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write edition support flags")
    args = parser.parse_args()
    settings = Settings()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.command == "compare":
        result = asyncio.run(evaluate_modes(settings, cases))
    else:
        if not args.catalog:
            parser.error("--catalog required")
        evaluation = (json.loads(args.evaluation.read_text(encoding="utf-8")) if args.evaluation
                      else asyncio.run(evaluate_modes(settings, cases)))
        result = audit(settings, load_catalog(args.catalog), cases, evaluation, apply=args.apply)
    save_json(args.output, result)
    print(json.dumps({"output": str(args.output), "command": args.command}))


if __name__ == "__main__":
    main()
