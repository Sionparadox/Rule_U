"""Opt-in live latency measurement (NF2001, with NF2002 cache reuse).

Each representative question is answered twice through the real retrieve -> generate graph.
The first run starts without the cached question embedding; the second reuses it. Stage times
come from the request diagnostics (retrieve_seconds, generate_seconds). Optionally, document
discovery (prompt 1 search terms + prompt 2 selection) is run cold and then from its cache."""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine, make_sessions
from rule_u.discovery import discover, inventory, normalize
from rule_u.ingestion import digest, load_catalog, save_json, vector_collections
from rule_u.models import Edition, Game
from rule_u.rag import answer_question


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def summary(values):
    return {"n": len(values), "p50": round(statistics.median(values), 3),
            "p95": round(percentile(values, 0.95), 3), "max": round(max(values), 3)}


async def answer_runs(settings, sessions, cases):
    fingerprint = vector_collections(settings)[0]
    runs = []
    for case in cases:
        cache = settings.data_dir / "query-cache" / (
            digest((fingerprint + normalize(case["question"])).encode()) + ".json")
        cache.unlink(missing_ok=True)  # the first run must embed the question itself
        with sessions() as db:
            game, edition = db.get(Game, case["game_id"]), db.get(Edition, case["edition_id"])
            context = {"game": {"id": game.id, "name": game.name_ko, "description": game.description},
                       "edition": {"id": edition.id, "label": edition.label,
                                   "language": edition.language},
                       "expansion_ids": [], "mode": "ruling",
                       "messages": [{"role": "user", "content": case["question"]}]}
        for attempt in ("first", "second"):
            started = time.perf_counter()
            result = await asyncio.wait_for(answer_question(settings, sessions, context), 120)
            total = time.perf_counter() - started
            detail = result.get("diagnostic_detail", {})
            runs.append({"game_id": case["game_id"], "kind": case["kind"], "run": attempt,
                         "total_seconds": round(total, 3),
                         "retrieve_seconds": detail.get("retrieve_seconds"),
                         "generate_seconds": detail.get("generate_seconds"),
                         "verdict": result["verdict"]})
            print(json.dumps(runs[-1]), flush=True)
    return runs


async def discovery_runs(settings, catalog, reviews, game_id, question):
    rows = load_catalog(catalog)
    registry = inventory(settings, rows, json.loads(reviews.read_text(encoding="utf-8")))
    row = next(r for r in rows if r["slug"] == game_id)
    edition = row["editions"][0]["id"]
    probe = await discover(settings, registry, game_id, edition, question)
    (settings.data_dir / "discovery-cache" / f"{probe['cache_key']}.json").unlink()
    runs = []
    for attempt in ("cold", "cached"):
        started = time.perf_counter()
        result = await discover(settings, registry, game_id, edition, question)
        runs.append({"run": attempt, "seconds": round(time.perf_counter() - started, 3),
                     "cache_hit": result["cache_hit"], "terms": result["terms"],
                     "fallback_terms": result["fallback_terms"],
                     "selected": [{"id": d["id"], "title": d["title"], "type": d["type"],
                                   "reason": d["selection_reason"]} for d in result["selected"]],
                     "excluded": result["excluded"], "status": result["status"]})
        print(json.dumps({k: runs[-1][k] for k in ("run", "seconds", "cache_hit")}), flush=True)
    return {"game_id": game_id, "edition_id": edition, "question": question, "runs": runs}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--kinds", nargs="+", default=["exception", "no_evidence"])
    parser.add_argument("--per-kind", type=int, default=0, help="limit cases per kind (0 = all)")
    parser.add_argument("--catalog", type=Path, default=ROOT.parent / "data" / "games")
    parser.add_argument("--reviews", type=Path, default=ROOT / "config" / "source-reviews.json")
    parser.add_argument("--discovery-game", default="catan")
    parser.add_argument("--discovery-question", default="도둑을 옮길 때 자원카드를 빼앗는 규칙")
    parser.add_argument("--output", default="latency.json", help="file name under the data directory")
    args = parser.parse_args()
    settings = Settings()
    if settings.chat_provider != "compatible" or settings.embedding_provider != "compatible":
        raise ValueError("live_providers_required")
    settings.bgg_enabled = False  # measure the local pipeline; BGG adds its own throttled calls
    cases = json.loads((ROOT / "evals/stage5-core-answer-cases.json").read_text(encoding="utf-8"))
    picked, counts = [], {}
    for case in cases:
        if case["kind"] in args.kinds and (not args.per_kind or counts.get(case["kind"], 0) < args.per_kind):
            counts[case["kind"]] = counts.get(case["kind"], 0) + 1
            picked.append(case)
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    try:
        runs = await answer_runs(settings, sessions, picked)
    finally:
        engine.dispose()
    report = {"search_mode": settings.search_mode, "chat_model": settings.chat_model,
              "runs": runs, "summary": {
                  run: {key: summary([r[key] for r in runs if r["run"] == run and r[key] is not None])
                        for key in ("total_seconds", "retrieve_seconds", "generate_seconds")}
                  for run in ("first", "second")}}
    if args.discovery_game:
        report["discovery"] = await discovery_runs(settings, args.catalog, args.reviews,
                                                   args.discovery_game, args.discovery_question)
    save_json(settings.data_dir / args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
