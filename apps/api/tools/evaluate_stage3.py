"""Opt-in live RAG smoke evaluation; writes local evidence for manual review."""
import argparse
import asyncio
import json

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import save_json
from rule_u.models import Edition, Game
from rule_u.rag import answer_question


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--resume", action="store_true",
                        help="Continue a partial run after verifying its case prefix")
    args = parser.parse_args()
    settings = Settings()
    if settings.chat_provider != "compatible" or settings.embedding_provider != "compatible":
        raise ValueError("live_providers_required")
    cases = json.loads((ROOT / "evals/retrieval-smoke-cases.json").read_text(encoding="utf-8"))[:3]
    cases += [{**cases[0], "question": "이 카드를 지금 써도 되나요?", "pages": []},
              {**cases[0], "question": "공식 대회 우승자의 상금은 얼마인가요?", "pages": []}]
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    output = settings.data_dir / "stage3-live-evaluation.json"
    results = json.loads(output.read_text(encoding="utf-8")) if args.resume else []
    if len(results) > len(cases) or [r["case"] for r in results] != cases[:len(results)]:
        raise ValueError("resume_cases_mismatch")
    try:
        for case in cases[len(results):]:
            with sessions() as db:
                game, edition = db.get(Game, case["game_id"]), db.get(Edition, case["edition_id"])
                context = {"game": {"id": game.id, "name": game.name_ko, "description": game.description},
                           "edition": {"id": edition.id, "label": edition.label, "language": edition.language},
                           "expansion_ids": [], "mode": "ruling", "messages": [
                               {"role": "user", "content": case["question"]}]}
            result = await asyncio.wait_for(answer_question(settings, sessions, context), 120)
            results.append({"case": case, "result": result})
            save_json(output, results)
            print(json.dumps({"case": len(results), "verdict": result["verdict"],
                              "citations": len(result["citations"])}, ensure_ascii=True), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
