"""Opt-in live answer evaluation for core games, per search mode. BGG fallback is off so the
result measures rulebook retrieval only. Writes local evidence for manual review."""
import argparse
import asyncio
import json

from rule_u.config import ROOT, Settings
from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import save_json
from rule_u.models import Edition, Game
from rule_u.providers import chat_provider
from rule_u.rag import answer_question


class Recording:
    """Keeps raw model output so refusals can be told apart from validation rejections."""

    def __init__(self, provider):
        self.provider, self.raw = provider, []

    async def generate(self, messages):
        value = await self.provider.generate(messages)
        self.raw.append(value)
        return value


def judged(case, result):
    if result["verdict"] not in case["expected_verdicts"]:
        return False
    if not case["pages"]:
        return True
    return any(c["page_start"] in case["pages"] for c in result["citations"])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--modes", nargs="+", default=["similarity", "hybrid"])
    parser.add_argument("--resume", action="store_true",
                        help="Continue a partial run after verifying its prefix")
    args = parser.parse_args()
    settings = Settings()
    if settings.chat_provider != "compatible" or settings.embedding_provider != "compatible":
        raise ValueError("live_providers_required")
    settings.bgg_enabled = False
    cases = json.loads((ROOT / "evals/stage5-core-answer-cases.json").read_text(encoding="utf-8"))
    plan = [(mode, case) for mode in args.modes for case in cases]
    output = settings.data_dir / "stage5-answer-evaluation.json"
    results = json.loads(output.read_text(encoding="utf-8")) if args.resume else []
    if [(r["mode"], r["case"]) for r in results] != plan[:len(results)]:
        raise ValueError("resume_cases_mismatch")
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    try:
        for mode, case in plan[len(results):]:
            settings.search_mode = mode
            with sessions() as db:
                game, edition = db.get(Game, case["game_id"]), db.get(Edition, case["edition_id"])
                context = {"game": {"id": game.id, "name": game.name_ko, "description": game.description},
                           "edition": {"id": edition.id, "label": edition.label, "language": edition.language},
                           "expansion_ids": [], "mode": "ruling", "messages": [
                               {"role": "user", "content": case["question"]}]}
            provider = Recording(chat_provider(settings))
            result = await asyncio.wait_for(
                answer_question(settings, sessions, context, provider), 120)
            results.append({"mode": mode, "case": case, "passed": judged(case, result),
                            "result": result, "raw_outputs": provider.raw})
            save_json(output, results)
            print(json.dumps({"n": len(results), "mode": mode, "kind": case["kind"],
                              "verdict": result["verdict"], "passed": results[-1]["passed"]}),
                  flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
