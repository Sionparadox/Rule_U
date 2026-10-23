import asyncio
import hashlib
import json

import pymupdf
import pytest
from test_ingestion import bundle

from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import import_metadata, index_bundle, ingest_documents, vector_collections
from rule_u.models import Edition
from rule_u.rag import admitted_supplements, retrieve
from rule_u.search import bm25_ranking, mmr, rrf, search, tokens
from rule_u.stage5 import audit, evaluate_modes, text_quality

PAGES = ["Setup: shuffle the deck and deal five cards to each player.",
         "Trading: only the active player may trade resources with others.",
         "Robber: when a seven is rolled, move the robber and steal one card."]


def rule_bundle(tmp_path):
    """A rulebook PDF plus the FAQ fixture, both scoped to test-edition."""
    rows = bundle(tmp_path)
    pdf = pymupdf.open()
    for text in PAGES:
        pdf.new_page().insert_text((72, 72), text)
    path = tmp_path / "rules.pdf"
    pdf.save(path)
    rows[0]["editions"][0]["documents"].append({
        "type": "rulebook", "status": "downloaded", "local_path": "rules.pdf",
        "source_type": "publisher", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


def indexed(settings, tmp_path):
    rows = rule_bundle(tmp_path)
    import_metadata(settings, rows)
    report = ingest_documents(settings, rows, tmp_path)
    asyncio.run(index_bundle(settings, rows))
    ids = {r["document_type"]: r["document_id"] for r in report}
    return rows, ids


def context(question="Who may trade?"):
    return {"game": {"id": "test-game"}, "edition": {"id": "test-edition", "label": "Test"},
            "expansion_ids": [], "messages": [{"role": "user", "content": question}]}


def test_tokens_keyword_ranking_and_rrf():
    assert "거래" in tokens("거래하기") and "하기" in tokens("거래하기")
    docs = ["setup and shuffle", "only the active player may trade", "robber steals"]
    assert bm25_ranking("Who may trade?", docs)[0] == 1
    assert bm25_ranking("unrelated", docs) == []
    # A document ranked well in both lists wins over one ranked first in only one.
    assert rrf([["a", "b", "c"], ["b", "c", "a"]])[0] == "b"


def test_mmr_prefers_diverse_results():
    # The near-duplicate of the first pick loses to a less relevant but different chunk.
    vectors = [[0.9, 0.1], [0.89, 0.11], [0.7, -0.7]]
    assert mmr([1.0, 0.0], vectors, 2) == [0, 2]


def test_all_modes_share_scoped_chunks(configured, tmp_path):
    settings, _ = configured
    indexed(settings, tmp_path)
    _, collections = vector_collections(settings)
    where = {"$and": [{"game_id": "test-game"}, {"edition_id": "test-edition"}]}
    scoped = set(collections["rule_docs"].get(where=where, include=[])["ids"])
    vector = [0.1] * settings.embedding_dimensions
    for mode in ("similarity", "hybrid", "mmr"):
        found = search(collections["rule_docs"], vector, "active player trade", where, mode, 3, 20)
        assert found and {m["chunk_id"] for m, _ in found} <= {
            m["chunk_id"] for m in collections["rule_docs"].get(ids=list(scoped))["metadatas"]}
    # The only chunk matching every keyword cannot rank lower than in vector-only search.
    ranks = {}
    for mode in ("similarity", "hybrid"):
        found = search(collections["rule_docs"], vector, "active player trade", where, mode, 3, 20)
        ranks[mode] = next(i for i, (_, text) in enumerate(found) if "active player" in text)
    assert ranks["hybrid"] <= ranks["similarity"]
    with pytest.raises(ValueError):
        search(collections["rule_docs"], vector, "x", where, "keyword_only", 3, 20)


def test_supplement_requires_verified_relation():
    docs = {"rules": {}, "faq": {}}
    types = {"rules": "rulebook", "faq": "faq"}
    relation = {"type": "faq", "status": "verified", "edition_id": "ed",
                "amends_document_id": "rules"}
    assert admitted_supplements(docs, types, {}, "ed")[1] == {}
    assert admitted_supplements(docs, types, {"faq": {**relation, "status": "unverified"}}, "ed")[1] == {}
    assert admitted_supplements(docs, types, {"faq": relation}, "other")[1] == {}
    assert admitted_supplements(docs, types, {"faq": {**relation, "type": "errata"}}, "ed")[1] == {}
    assert admitted_supplements(docs, types, {"faq": {**relation, "amends_document_id": "x"}},
                                "ed")[1] == {}
    assert set(admitted_supplements(docs, types, {"faq": relation}, "ed")[1]) == {"faq"}


def test_retrieve_joins_faq_only_with_relation(configured, tmp_path):
    settings, _ = configured
    settings.document_relations_path = tmp_path / "relations.json"
    _, ids = indexed(settings, tmp_path)
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    for mode in ("similarity", "hybrid", "mmr"):
        settings.search_mode = mode
        found = asyncio.run(retrieve(settings, sessions, context()))
        assert found and {e["document_id"] for e in found} == {ids["rulebook"]}
    settings.document_relations_path.write_text(json.dumps({ids["faq"]: {
        "type": "faq", "status": "verified", "edition_id": "test-edition",
        "amends_document_id": ids["rulebook"], "evidence": "test"}}), encoding="utf-8")
    settings.search_mode = "hybrid"
    found = asyncio.run(retrieve(settings, sessions, context("When after your turn?")))
    faq = [e for e in found if e["document_id"] == ids["faq"]]
    assert faq and faq[0]["supplement_type"] == "faq"
    assert faq[0]["amends_document_id"] == ids["rulebook"]
    engine.dispose()


def test_text_quality_flags_garbled_and_table_pages():
    good = {"page": 1, "text": "자기 차례에는 카드 한 장을 냅니다. You may trade."}
    noise = {"page": 2, "text": "ѱ੐੄ݾ੸ ѱ੐ࢸ੿ ఐ೷о۽੉ܖয"}
    table = {"page": 3, "text": "8 5 3 2 1 -1 8 5 3 2 1 -1 8 5 3 2 1 -1"}
    assert text_quality([good, good, noise])["status"] == "readable"
    result = text_quality([good, noise, table])
    assert result["status"] == "garbled" and result["unreadable_pages"] == [2, 3]


def test_mode_comparison_and_support_audit(configured, tmp_path):
    settings, _ = configured
    rows, ids = indexed(settings, tmp_path)
    cases = [{"game_id": "test-game", "edition_id": "test-edition",
              "document_id": ids["rulebook"], "question": "Who may trade resources?", "pages": [2]}]
    evaluation = asyncio.run(evaluate_modes(settings, cases))
    assert set(evaluation["summary"]) == {"similarity", "hybrid", "mmr"}
    assert evaluation["cases"][0]["modes"]["hybrid"]["rank"] == 1
    assert asyncio.run(evaluate_modes(settings, cases))["cases"][0]["cache_hit"]
    dry = audit(settings, rows, cases, evaluation)
    assert dry["supported_games"] == 1 and not dry["applied"]
    engine = make_engine(settings)
    with make_sessions(engine)() as db:
        assert db.get(Edition, "test-edition").supported is False
    result = audit(settings, rows, cases, evaluation, apply=True)
    assert result["items"][0]["reasons"] == []
    with make_sessions(engine)() as db:
        assert db.get(Edition, "test-edition").supported is True
    # Without a grounding question the edition is excluded from support totals.
    result = audit(settings, rows, [], {"cases": []}, apply=True)
    assert result["supported_games"] == 0
    assert result["items"][0]["reasons"] == ["grounding_question_missing"]
    with make_sessions(engine)() as db:
        assert db.get(Edition, "test-edition").supported is False
    engine.dispose()
