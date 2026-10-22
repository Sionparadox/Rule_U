import asyncio

import pytest

from rule_u.discovery import discover, inventory


class FakeChat:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = 0

    async def generate(self, messages):
        self.calls += 1
        return next(self.answers)


def documents():
    base = {"game_id": "a", "edition_id": "a-ko", "expansion_ids": [],
            "game_name": "게임", "aliases": [], "title": "규칙", "type": "rulebook",
            "source_review": "unverified", "sha256": "original"}
    return [dict(base, id="own"), dict(base, id="faq", type="faq",
                                     source_review="official_verified"),
            dict(base, id="other", edition_id="a-en")]


def test_discovery_scopes_mandatory_rules_cache_and_invalidation(configured):
    settings, _ = configured
    registry = documents()
    chat = FakeChat(['{"terms":["종료"]}', '{"selected_ids":[]}'])
    result = asyncio.run(discover(settings, registry, "a", "a-ko", "종료?", provider=chat))
    assert [d["id"] for d in result["selected"]] == ["own"]
    assert {d["id"] for d in result["excluded"]} == {"other", "faq"}
    again = asyncio.run(discover(settings, registry, "a", "a-ko", "종료?", provider=chat))
    assert again["cache_hit"] and chat.calls == 2
    registry[0]["sha256"] = "changed"
    replacement = FakeChat(['{"terms":["종료"]}', '{"selected_ids":["other"]}'])
    result = asyncio.run(discover(settings, registry, "a", "a-ko", "종료?", provider=replacement))
    assert not result["cache_hit"] and result["fallback_selection"]
    assert {d["id"] for d in result["selected"]} == {"own", "faq"}
    with pytest.raises(ValueError, match="unregistered_expansion"):
        asyncio.run(discover(settings, registry, "a", "a-ko", "질문", ["unknown"]))


def test_invalid_llm_output_has_bounded_fallback(configured):
    chat = FakeChat(["bad", '{"terms":[""]}', "bad", "bad"])
    result = asyncio.run(discover(configured[0], documents(), "a", "a-ko", "질문", provider=chat))
    assert result["fallback_terms"] and result["fallback_selection"]
    assert chat.calls == 4
    assert result["terms"] == ["게임", "질문"]


def test_source_review_requires_exact_hash(configured):
    from rule_u.ingestion import digest

    row = {"slug": "a", "name_ko": "게임", "editions": [{"id": "a-ko", "name": "판본",
           "language": "ko", "documents": [{"local_path": "a.pdf", "sha256": "new"}]}]}
    review = {digest(b"a-ko:a.pdf"): {"sha256": "old", "status": "official_verified"}}
    result = inventory(configured[0], [row], review)
    assert result[0]["source_review"] == "unverified"


def test_collection_preserves_unselected_manifest_and_catalog(configured, monkeypatch):
    import json

    from rule_u import discovery
    from rule_u.ingestion import digest, save_json

    settings, _ = configured
    source_id = digest(b"ko:a.pdf")
    rows = [{"slug": "a", "editions": [{"id": "ko", "documents": [
        {"local_path": "a.pdf"}, {"local_path": "faq.json"}]}]}]
    path = settings.data_dir / "manifests/a.json"
    save_json(path, [{"source_id": "sibling", "status": "extracted"}])

    def fake_ingest(settings, subset, *args):
        assert len(subset[0]["editions"][0]["documents"]) == 1
        result = [{"source_id": source_id, "status": "extracted"}]
        save_json(path, result)
        return result

    monkeypatch.setattr(discovery, "ingest_documents", fake_ingest)
    discovery.collect_selected(settings, rows, [{"id": source_id}], settings.data_dir)
    assert len(json.loads(path.read_text())) == 2
    assert json.loads((settings.data_dir / "catalog/a.json").read_text()) == rows[0]
