"""Record how retrieval settings change results (F2005 chunking, F2006 Top-k).

Chunking: re-chunks already extracted pages with several size/overlap pairs. This is local and
makes no embedding calls. Top-k: runs the same questions with several external_top_k values
over the active index and lists the returned evidence. It needs the configured embedding
provider only for questions whose embedding is not cached yet."""
import argparse
import asyncio
import json

from sqlalchemy import select

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import chunks_for, save_json
from rule_u.models import Document, DocumentScope, Edition, Game
from rule_u.rag import retrieve

CHUNK_SETTINGS = [(500, 100), (1000, 200), (1500, 300)]


def chunk_comparison(settings, sessions, edition_ids):
    rows = []
    with sessions() as db:
        for edition_id in edition_ids:
            for scope in db.scalars(select(DocumentScope).where(DocumentScope.edition_id == edition_id)):
                document = db.get(Document, scope.document_id)
                artifact = json.loads((settings.data_dir / document.extracted_text_key)
                                      .read_text(encoding="utf-8"))
                counts = {f"{size}/{overlap}": len(chunks_for(artifact["pages"], document.id,
                                                              size, overlap))
                          for size, overlap in CHUNK_SETTINGS}
                rows.append({"edition_id": edition_id, "title": document.title,
                             "pages": len(artifact["pages"]), "chunks": counts,
                             "active_index_chunks": len(artifact["chunks"])})
    return rows


async def top_k_comparison(settings, sessions, cases, values):
    rows = []
    for case in cases:
        with sessions() as db:
            game, edition = db.get(Game, case["game_id"]), db.get(Edition, case["edition_id"])
            context = {"game": {"id": game.id}, "edition": {"id": edition.id, "label": edition.label},
                       "expansion_ids": [], "messages": [{"role": "user", "content": case["question"]}]}
        by_k = {}
        for k in values:
            settings.external_top_k = k
            found = await retrieve(settings, sessions, context)
            by_k[str(k)] = [{"number": e["number"], "page": e["page_start"],
                             "chunk_id": e["chunk_id"]} for e in found]
        rows.append({"game_id": case["game_id"], "question": case["question"],
                     "answer_pages": case["pages"], "by_k": by_k})
    return rows


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", nargs="+", type=int, default=[3, 5, 8])
    parser.add_argument("--output", default="settings-comparison.json",
                        help="file name under the data directory")
    args = parser.parse_args()
    settings = Settings()
    cases = [c for c in json.loads((ROOT / "evals/stage5-core-answer-cases.json")
                                   .read_text(encoding="utf-8")) if c["kind"] == "exception"]
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    try:
        report = {
            "search_mode": settings.search_mode,
            "chunking": chunk_comparison(settings, sessions, sorted({c["edition_id"] for c in cases})),
            "top_k": await top_k_comparison(settings, sessions, cases, args.top_k),
        }
    finally:
        engine.dispose()
    save_json(settings.data_dir / args.output, report)
    print(json.dumps({"chunking": [(r["title"], r["chunks"]) for r in report["chunking"]],
                      "top_k": [(r["game_id"], {k: len(v) for k, v in r["by_k"].items()})
                                for r in report["top_k"]]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
