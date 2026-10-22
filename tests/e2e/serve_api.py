"""Isolated E2E database, never the developer's data/app.db."""
import os
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic import command
from alembic.config import Config

from rule_u.cli import seed
from rule_u.config import ROOT, Settings
from rule_u.main import create_app
from rule_u.models import Document, Edition, Expansion, Game, expansion_editions
from rule_u.providers import ProviderError


class FixtureProvider:

    async def generate(self, messages):
        context = json.loads(messages[-1]["content"])
        explanation = {"source_number": 1,
                       "rule_summary": "카드는 자신의 턴이 끝난 뒤에 사용할 수 있는 규칙입니다.",
                       "application": "질문에서는 이미 턴이 끝났으므로, 이 사용 시점 조건을 충족한다고 답변했어요.",
                       "supporting_quote": "자신의 턴 이후에만 사용합니다."}
        if "answer" in context:
            return json.dumps(explanation)
        question = context["messages"][-1]["content"]
        if "실패 테스트" in question and sum("실패 테스트" in m["content"] for m in context["messages"] if m["role"] == "user") == 1:
            raise ProviderError("provider_call_failed")
        if "정보 부족" in question:
            return json.dumps({"answer": "정보 필요", "verdict": "needs_clarification",
                               "cited_ids": [], "clarification": "어떤 카드이며 누구의 턴인가요?"})
        return json.dumps({"answer": "자신의 턴이 끝난 뒤 사용할 수 있어요. [1]",
                           "verdict": "conditional", "cited_ids": [1], "clarification": "",
                           "explanations": [explanation]})


async def fixture_retrieve(settings, sessions, context):
    question = context["messages"][-1]["content"]
    await asyncio.sleep(3 if "느린 질문" in question else .4)
    if "근거 없음" in question:
        return []
    return [{"number": 1, "document_id": "fixture-doc", "chunk_id": "fixture-chunk",
             "source_version": "v1", "title_snapshot": "테이블 탐험 규칙서",
             "source_url_snapshot": "https://example.test/rules", "edition_snapshot": "한국어 기본판",
             "page_start": 2, "page_end": 2, "excerpt": "자신의 턴 이후에만 사용합니다.",
             "language": "ko", "source_type": "user_provided", "extraction_method": "text",
             "review_note": "브라우저 검증용 가상 자료"}]


async def fixture_rank(*args):
    return ["table-game", "second-game"]

with TemporaryDirectory(prefix="rule-u-e2e-") as folder:
    os.environ["DATA_DIR"] = folder
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(folder).as_posix()}/app.db"
    os.environ["CHAT_PROVIDER"] = "mock"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    command.upgrade(Config(str(ROOT / "apps/api/alembic.ini")), "head")
    settings = Settings(_env_file=None)
    seed(settings)
    application = create_app(settings, provider=FixtureProvider(), retriever=fixture_retrieve,
                             game_ranker=fixture_rank)
    with application.state.sessions.begin() as db:
        for gid, name in [("table-game", "테이블 탐험"), ("second-game", "숲속 산책")]:
            db.add(Game(id=gid, name_ko=name, min_players=2, max_players=4, min_minutes=20,
                        max_minutes=30, categories=["전략"]))
            db.flush()
            db.add(Edition(id=gid+"-ko", game_id=gid, label="한국어 기본판", language="ko", supported=True))
        db.flush()
        db.add(Expansion(id="table-exp", game_id="table-game", name="야간 탐험", supported=True))
        db.flush()
        db.execute(expansion_editions.insert().values(expansion_id="table-exp", edition_id="table-game-ko", game_id="table-game"))
        db.add(Document(id="fixture-doc", title="테이블 탐험 규칙서", source_type="user_provided",
                        source_url="https://example.test/rules", storage_key="originals/fixture.pdf",
                        language="ko", version="v1", content_hash="fixture"))
    original = Path(folder)/"originals/fixture.pdf"
    original.parent.mkdir(exist_ok=True)
    original.write_bytes(b"%PDF-1.4 E2E fixture")
    uvicorn.run(application, host="127.0.0.1", port=8100)
