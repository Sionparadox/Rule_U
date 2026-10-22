import asyncio
import csv
import hashlib
import json

import pytest
from sqlalchemy import func, select

from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import (
    chunks_for,
    extract_pages,
    import_metadata,
    index_bundle,
    index_catalog,
    ingest_documents,
    load_catalog,
    local_file,
    vector_collections,
)
from rule_u.models import Document, DocumentScope, Edition, Game


def bundle(tmp_path):
    path = tmp_path / "faq.json"
    path.write_text(
        json.dumps([{"question": "When?", "answer": "After your turn. " * 100}]), encoding="utf-8"
    )
    return [
        {
            "id": 1,
            "slug": "test-game",
            "name_ko": "Test",
            "players": {"min": 2, "max": 4},
            "play_time_minutes": {"min": 10, "max": 20},
            "editions": [
                {
                    "id": "test-edition",
                    "name": "Test edition",
                    "language": "en",
                    "documents": [
                        {
                            "type": "faq",
                            "status": "downloaded",
                            "local_path": "faq.json",
                            "source_type": "user_provided",
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    ],
                }
            ],
        }
    ]


def test_metadata_json_csv_idempotent(configured, tmp_path):
    settings, _ = configured
    rows = bundle(tmp_path)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    import_metadata(settings, load_catalog(path))
    csv_path = tmp_path / "catalog.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerow(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in rows[0].items()}
        )
    import_metadata(settings, load_catalog(csv_path))
    engine = make_engine(settings)
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Game)) == 2  # includes demo
        assert db.get(Edition, "test-edition").supported is False
    engine.dispose()


def test_offsets_overlap_and_faq_units():
    text = "Rule. Exception.\n" * 180
    pages = [{"page": 3, "text": text, "locator": "page:3"}]
    chunks = chunks_for(pages, "doc", 1000, 200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["text"] == text[chunk["start"] : chunk["end"]]
        assert chunk["page_start"] == chunk["page_end"] == 3
    for left, right in zip(chunks, chunks[1:]):
        assert left["end"] - right["start"] == 200
    assert len(chunks_for(pages, "doc", faq=True)) == 1


def test_ingest_index_retry_hash_and_scope(configured, tmp_path):
    settings, _ = configured
    rows = bundle(tmp_path)
    first = ingest_documents(settings, rows, tmp_path)
    second = ingest_documents(settings, rows, tmp_path)
    assert first == second
    assert first[0]["chunks"] == 1
    assert first[0]["source_type"] == "user_provided"
    first_index = asyncio.run(index_bundle(settings, rows))
    second_index = asyncio.run(index_bundle(settings, rows))
    assert first_index["embedded"] == 2
    assert second_index["embedded"] == 0
    assert second_index["cached"] == 2
    _, collections = vector_collections(settings)
    assert collections["rule_docs"].get(where={"game_id": "other"})["ids"] == []
    engine = make_engine(settings)
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1
        assert db.scalar(select(func.count()).select_from(DocumentScope)) == 1
        assert db.get(Edition, "test-edition").supported is False
    engine.dispose()
    (tmp_path / "faq.json").write_text("tampered", encoding="utf-8")
    failed = ingest_documents(settings, rows, tmp_path)
    assert failed[0]["status"] == "failed"
    assert "hash" in failed[0]["error"]
    with pytest.raises(ValueError, match="game_has_failed_documents"):
        asyncio.run(index_bundle(settings, rows))
    assert collections["rule_docs"].count() == 1


def test_paths_and_model_isolation(configured, tmp_path):
    with pytest.raises(ValueError):
        local_file(tmp_path, "../outside.pdf")
    settings, _ = configured
    fingerprint, _ = vector_collections(settings)
    settings.embedding_dimensions += 1
    other, collections = vector_collections(settings)
    assert fingerprint != other
    assert collections["rule_docs"].count() == 0


def test_blank_pdf_is_not_supported(tmp_path):
    from pypdf import PdfWriter

    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(path)
    with pytest.raises(ValueError, match="empty_or_short_page"):
        extract_pages(path, "rulebook")


def test_catalog_continues_after_failed_game(configured, tmp_path):
    settings, _ = configured
    rows = bundle(tmp_path)
    ingest_documents(settings, rows, tmp_path)
    bad = dict(rows[0], slug="missing-game")
    report = asyncio.run(index_catalog(settings, [bad, *rows]))
    assert report["failed_games"] == 1
    assert report["indexed_games"] == 1
    assert report["games"][0]["error"].startswith("game_manifest_missing")
    assert report["counts"] == {"game_meta": 2, "rule_docs": 1}
    again = asyncio.run(index_catalog(settings, rows))
    assert again["games"][0]["embedded"] == 0


def test_skipped_pdf_content_is_rejected(tmp_path, monkeypatch):
    import logging
    from types import SimpleNamespace

    import rule_u.ingestion as ingestion

    class Page:
        def extract_text(self):
            logging.getLogger("pypdf").warning("Further form content is skipped.")
            return "Otherwise valid rule text " * 10

    monkeypatch.setattr(
        ingestion, "PdfReader", lambda _: SimpleNamespace(is_encrypted=False, pages=[Page()])
    )
    with pytest.raises(ValueError, match="pdf_content_skipped"):
        extract_pages(tmp_path / "test.pdf", "rulebook")


def test_alternate_pdf_extractor_preserves_pages(tmp_path):
    import pymupdf

    path = tmp_path / "rules.pdf"
    with pymupdf.open() as pdf:
        for text in ("First page rule and exception together.", "Second page scoring explanation."):
            pdf.new_page().insert_text((72, 72), text)
        pdf.save(path)
    pages = extract_pages(path, "rulebook", "pymupdf")
    assert [p["page"] for p in pages] == [1, 2]
    assert pages[1]["locator"] == "page:2"
    assert "scoring" in pages[1]["text"]
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(tmp_path / "blank-alternate.pdf")
    with pytest.raises(ValueError, match="empty_or_short_page"):
        extract_pages(tmp_path / "blank-alternate.pdf", "rulebook", "pymupdf")
