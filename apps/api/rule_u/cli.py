import argparse
import asyncio
import json
from pathlib import Path

from rule_u.config import Settings
from rule_u.db import make_engine, make_sessions
from rule_u.models import Edition, Game
from rule_u.providers import ProviderError, chat_provider, embedding_provider


def seed(settings):
    engine = make_engine(settings)
    with make_sessions(engine).begin() as db:
        if not db.get(Game, "demo-game"):
            db.add(
                Game(
                    id="demo-game",
                    name_ko="연결 확인용 샘플 게임",
                    description="저장 기능을 확인하는 가상 데이터입니다. 규칙 Q&A는 아직 지원하지 않습니다.",
                    external_source="test-fixture",
                    external_id="demo",
                )
            )
            db.flush()
            db.add(
                Edition(
                    id="demo-edition",
                    game_id="demo-game",
                    label="테스트 판본",
                    language="ko",
                    supported=False,
                )
            )
    engine.dispose()
    print("Demo game ready (rules unsupported).")


async def probe(settings, live):
    results = {}
    for kind, factory in [("chat", chat_provider), ("embedding", embedding_provider)]:
        mode = getattr(settings, f"{kind}_provider")
        if live and mode == "mock":
            results[kind] = {"status": "not_verified", "reason": "mock_selected"}
            continue
        try:
            provider = factory(settings)
            if kind == "chat":
                answer = await provider.generate(
                    [{"role": "user", "content": "Reply with OK only."}]
                )
                results[kind] = {
                    "status": "live_ok" if live else "mock_ok" if mode == "mock" else "live_ok",
                    "model": settings.chat_model if mode != "mock" else "mock",
                    "nonempty_response": bool(answer.strip()),
                }
            else:
                vectors = await provider.embed(["connection check", "dimension check"])
                results[kind] = {
                    "status": "mock_ok" if mode == "mock" else "live_ok",
                    "model": settings.embedding_model if mode != "mock" else "mock",
                    "dimensions": len(vectors[0]),
                    "count": len(vectors),
                }
        except ProviderError as exc:
            results[kind] = {"status": "failed", "reason": str(exc)}
    print(json.dumps(results, indent=2))
    return all(r["status"] in ("live_ok", "mock_ok") for r in results.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed-demo", "probe", "export-openapi"])
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "seed-demo":
        seed(settings)
    elif args.command == "probe":
        raise SystemExit(0 if asyncio.run(probe(settings, args.live)) else 1)
    else:
        from rule_u.main import create_app

        app = create_app(settings)
        Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
        app.state.engine.dispose()


if __name__ == "__main__":
    main()
