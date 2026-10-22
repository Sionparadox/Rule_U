import json

from fastapi.testclient import TestClient
from test_rag import evidence

from rule_u.main import create_app
from rule_u.models import Document
from rule_u.rag import EvidenceExplanation, GeneratedAnswer, validate_answer, verified_explanation


def explanation(**updates):
    return {"source_number": 1, "rule_summary": "턴이 끝난 뒤에 사용하는 규칙입니다.",
            "application": "턴이 끝났다는 조건 때문에 사용할 수 있다고 답했습니다.",
            "supporting_quote": "자신의 턴 이후에만 사용합니다.", **updates}


def test_explanation_requires_matching_source_and_verbatim_anchor():
    assert verified_explanation(EvidenceExplanation(**explanation()), evidence())
    assert not verified_explanation(EvidenceExplanation(**explanation(source_number=2)), evidence())
    assert not verified_explanation(EvidenceExplanation(**explanation(supporting_quote="언제든 사용할 수 있습니다.")), evidence())
    generated = GeneratedAnswer(answer="턴 이후에 가능합니다. [1]", verdict="conditional", cited_ids=[1],
                                explanations=[explanation()])
    result = validate_answer(generated, [evidence()])
    assert result["citations"][0]["explanation"]["rule_summary"] == explanation()["rule_summary"]
    generated.explanations = [EvidenceExplanation(**explanation(source_number=2))]
    assert validate_answer(generated, [evidence()])["citations"][0]["explanation"] is None


def test_legacy_explanation_cached_owned_and_persisted(configured):
    class Provider:
        calls = 0

        async def generate(self, messages):
            self.calls += 1
            content = json.loads(messages[-1]["content"])
            if "answer" in content:
                assert content["question"] == "턴이 끝났어요"
                assert content["evidence"]["excerpt"] == evidence()["excerpt"]
                return json.dumps(explanation())
            return json.dumps({"answer": "턴 이후에 가능합니다. [1]", "verdict": "conditional", "cited_ids": [1]})

    async def found(*args):
        return [evidence()]

    provider = Provider()
    app = create_app(configured[0], provider=provider, retriever=found)
    with app.state.sessions.begin() as db:
        db.add(Document(id="doc", title="규칙서", source_type="user_provided", source_url="https://example.test",
                        language="ko", version="v1", content_hash="explanation-fixture"))
    with TestClient(app) as client:
        cid = client.post("/api/v1/conversations", json={"game_id": "demo-game", "edition_id": "demo-edition"}).json()["conversation_id"]
        client.post(f"/api/v1/conversations/{cid}/messages", json={"message": "턴이 끝났어요", "client_request_id": "once"})
        source = client.get(f"/api/v1/conversations/{cid}").json()["messages"][-1]["citations"][0]
        assert source["explanation"] is None
        with TestClient(app) as stranger:
            assert stranger.post(f"/api/v1/sources/{source['id']}/explanation").status_code == 404
        result = client.post(f"/api/v1/sources/{source['id']}/explanation")
        assert result.status_code == 200
        assert result.json()["explanation"]["application"] == explanation()["application"]
        assert "supporting_quote" not in result.json()["explanation"]
        assert result.json()["source_review"] == "unverified"
        assert provider.calls == 2
        assert client.post(f"/api/v1/sources/{source['id']}/explanation").status_code == 200
        assert provider.calls == 2
        cookies = dict(client.cookies)
    with TestClient(create_app(configured[0])) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get(f"/api/v1/sources/{source['id']}").json()["explanation"] == result.json()["explanation"]
