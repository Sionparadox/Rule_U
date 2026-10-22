"""Local bundle ingestion. Original metadata and evidence are never overwritten."""

import csv
import hashlib
import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError
from sqlalchemy import select

from rule_u.db import make_engine, make_sessions
from rule_u.models import CollectionState, Document, DocumentScope, Edition, Game
from rule_u.providers import ProviderError, embedding_provider


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_catalog(path):
    """CSV uses JSON cells for nested fields, the same schema as the existing bundle."""
    path = Path(path)
    if path.is_dir():
        rows = [json.loads(p.read_text(encoding="utf-8-sig")) for p in sorted(path.glob("*.json"))]
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ("aliases", "players", "play_time_minutes", "categories", "editions"):
                if row.get(key):
                    row[key] = json.loads(row[key])
    else:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = rows if isinstance(rows, list) else [rows]
    seen = set()
    for row in rows:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", row["slug"]):
            raise ValueError("invalid_game_slug")
        if row["slug"] in seen:
            raise ValueError("duplicate_game_slug")
        seen.add(row["slug"])
        if not row.get("name_ko") or not row.get("editions"):
            raise ValueError("game_name_and_editions_required")
    return rows


def import_metadata(settings, rows):
    engine = make_engine(settings)
    try:
        with make_sessions(engine).begin() as db:
            for row in rows:
                game = db.get(Game, row["slug"])
                if game is None:
                    game = Game(id=row["slug"])
                    db.add(game)
                game.external_source = "local_catalog"
                game.external_id = str(row["id"])
                for field in ("name_ko", "name_original", "description"):
                    setattr(game, field, row.get(field) or "")
                for field in ("aliases", "categories"):
                    setattr(game, field, row.get(field) or [])
                game.min_players = row["players"]["min"]
                game.max_players = row["players"]["max"]
                game.min_minutes = row["play_time_minutes"]["min"]
                game.max_minutes = row["play_time_minutes"]["max"]
                game.source = "local_catalog"
                db.flush()
                for item in row["editions"]:
                    edition = db.get(Edition, item["id"])
                    if edition is not None and edition.game_id != game.id:
                        raise ValueError("edition_game_mismatch")
                    if edition is None:
                        edition = Edition(id=item["id"], game_id=game.id, supported=False)
                        db.add(edition)
                    edition.label = item["name"]
                    edition.language = item["language"]
                    edition.publisher = item.get("publisher") or ""
        # Keep all source fields, including rights, provenance and unknown edition details.
        for row in rows:
            save_json(settings.data_dir / "catalog" / f"{row['slug']}.json", row)
    finally:
        engine.dispose()
    return {"games": len(rows), "editions": sum(len(r["editions"]) for r in rows)}


def local_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("document_path_outside_bundle_or_missing")
    return path


def extract_pages(path, kind, pdf_extractor="pypdf"):
    if kind == "faq":
        entries = json.loads(path.read_text(encoding="utf-8-sig"))
        return [
            {"page": n, "text": f"Q: {r['question']}\nA: {r['answer']}", "locator": f"faq:{n}"}
            for n, r in enumerate(entries, 1)
        ]
    if pdf_extractor == "pymupdf":
        import pymupdf

        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise ValueError("encrypted_pdf")
            pages = [
                {"page": n, "text": page.get_text(), "locator": f"page:{n}"}
                for n, page in enumerate(document, 1)
            ]
        if not pages or any(len(p["text"].strip()) < 20 for p in pages):
            raise ValueError("empty_or_short_page_needs_review")
        return pages
    if pdf_extractor != "pypdf":
        raise ValueError("unknown_pdf_extractor")
    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("encrypted_pdf")
    warnings = []

    class ExtractionWarnings(logging.Handler):
        def emit(self, record):
            warnings.append(record.getMessage())

    logger = logging.getLogger("pypdf")
    handler = ExtractionWarnings()
    logger.addHandler(handler)
    try:
        pages = [
            {"page": n, "text": page.extract_text() or "", "locator": f"page:{n}"}
            for n, page in enumerate(reader.pages, 1)
        ]
    finally:
        logger.removeHandler(handler)
    if any("skipped" in warning.lower() for warning in warnings):
        raise ValueError("pdf_content_skipped_needs_review")
    if not pages or any(len(p["text"].strip()) < 20 for p in pages):
        # Do not silently count scanned or missing pages as complete rule support.
        raise ValueError("empty_or_short_page_needs_review")
    return pages


def chunks_for(pages, document_id, size=1000, overlap=200, faq=False):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("invalid_chunk_settings")
    chunks = []
    for page in pages:
        text = page["text"]
        start = 0
        while start < len(text):
            end = len(text) if faq else min(start + size, len(text))
            if end < len(text):
                # Prefer paragraph/line boundaries; offsets still refer to exact extracted text.
                boundary = text.rfind("\n", start + size // 2, end)
                if boundary > start + overlap:
                    end = boundary + 1
            content = text[start:end]
            if content.strip():
                key = f"{document_id}:{page['page']}:{start}:{end}:{digest(content.encode())}"
                chunks.append(
                    {
                        "id": digest(key.encode()),
                        "document_id": document_id,
                        "page_start": page["page"],
                        "page_end": page["page"],
                        "locator": page["locator"],
                        "start": start,
                        "end": end,
                        "text": content,
                        **{k: page[k] for k in ("extraction_method", "review_note") if k in page},
                    }
                )
            if end == len(text):
                break
            start = end - overlap
    return chunks


def ingest_documents(settings, rows, bundle_root, pdf_extractor="pypdf", reviewed_path=None):
    import_metadata(settings, rows)
    engine = make_engine(settings)
    report = []
    if pdf_extractor not in ("pypdf", "pymupdf"):
        raise ValueError("unknown_pdf_extractor")
    extractor_version = "pypdf-v2-fonttools" if pdf_extractor == "pypdf" else "pymupdf-v1"
    config = f"{extractor_version}:{settings.chunk_size}:{settings.chunk_overlap}"
    reviews = None
    if reviewed_path is not None:
        review_raw = Path(reviewed_path).read_bytes()
        reviews = json.loads(review_raw)
        config += f":visual-v1:{digest(review_raw)}"
    try:
        for row in rows:
            for edition in row["editions"]:
                for item in edition.get("documents", []):
                    if item.get("status") != "downloaded":
                        continue
                    source_id = digest((edition["id"] + ":" + item["local_path"]).encode())
                    result = {
                        "game_id": row["slug"],
                        "edition_id": edition["id"],
                        "source_id": source_id,
                        "source_url": item.get("source_url"),
                        "source_type": item.get("source_type") or "unverified",
                        "license_note": item.get("license_note") or "이용 조건 미확인",
                        "document_type": item.get("type"),
                        "status": "failed",
                    }
                    try:
                        path = local_file(bundle_root, item["local_path"])
                        raw = path.read_bytes()
                        content_hash = digest(raw)
                        if not item.get("sha256") or content_hash != item["sha256"]:
                            raise ValueError("source_hash_missing_or_mismatch")
                        document_id = content_hash
                        artifact_key = digest(f"{document_id}:{config}:{item.get('type')}".encode())
                        extracted = settings.data_dir / "extracted" / f"{artifact_key}.json"
                        if extracted.exists():
                            artifact = json.loads(extracted.read_text(encoding="utf-8"))
                        else:
                            if reviews is not None and item.get("type") != "faq":
                                from rule_u.reviewed_pdf import reviewed_pages

                                pages = reviewed_pages(path, reviews)
                            else:
                                pages = extract_pages(path, item.get("type"), pdf_extractor)
                            if item.get("page_count") and len(pages) != item["page_count"]:
                                raise ValueError("page_count_mismatch")
                            chunks = chunks_for(
                                pages,
                                document_id,
                                settings.chunk_size,
                                settings.chunk_overlap,
                                item.get("type") == "faq",
                            )
                            artifact = {
                                "document_id": document_id,
                                "config": config,
                                "pages": pages,
                                "chunks": chunks,
                            }
                            save_json(extracted, artifact)
                        original = settings.data_dir / "originals" / (content_hash + path.suffix)
                        if not original.exists():
                            original.write_bytes(raw)
                        with make_sessions(engine).begin() as db:
                            document = db.scalar(
                                select(Document).where(Document.content_hash == content_hash)
                            )
                            if document is None:
                                document = Document(
                                    id=document_id,
                                    title=edition["name"],
                                    source_type=result["source_type"],
                                    source_url=item.get("source_url") or "",
                                    storage_key=original.relative_to(settings.data_dir).as_posix(),
                                    language=item.get("language") or edition["language"],
                                    version=content_hash,
                                    content_hash=content_hash,
                                    license_note=result["license_note"],
                                )
                                db.add(document)
                            document.extracted_text_key = extracted.relative_to(
                                settings.data_dir
                            ).as_posix()
                            db.flush()
                            scope_id = digest(f"{document.id}:{edition['id']}".encode())
                            if db.get(DocumentScope, scope_id) is None:
                                db.add(
                                    DocumentScope(
                                        id=scope_id,
                                        document_id=document.id,
                                        game_id=row["slug"],
                                        edition_id=edition["id"],
                                    )
                                )
                            state_id = digest(f"{source_id}:{config}".encode())
                            state = db.get(CollectionState, state_id)
                            if state is None:
                                state = CollectionState(
                                    id=state_id,
                                    source_id=source_id,
                                    game_id=row["slug"],
                                    edition_id=edition["id"],
                                    config_version=config,
                                )
                                db.add(state)
                            state.fetch_status = "extracted"
                            state.content_hash = content_hash
                        result.update(
                            status="extracted",
                            document_id=document_id,
                            extracted_key=extracted.relative_to(settings.data_dir).as_posix(),
                            pages=len(artifact["pages"]),
                            chunks=len(artifact["chunks"]),
                        )
                    except (ValueError, OSError, KeyError, PyPdfError, DependencyError) as exc:
                        result["error"] = type(exc).__name__ + ": " + str(exc)
                    report.append(result)
            save_json(
                settings.data_dir / "manifests" / f"{row['slug']}.json",
                [r for r in report if r["game_id"] == row["slug"]],
            )
    finally:
        engine.dispose()
    # Per-game manifests avoid dropping earlier runs when ingesting a subset.
    for row in rows:
        save_json(
            settings.data_dir / "manifests" / f"{row['slug']}.json",
            [r for r in report if r["game_id"] == row["slug"]],
        )
    return report


def vector_collections(settings):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    identity = json.dumps(
        {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "url": settings.embedding_base_url,
            "dimensions": settings.embedding_dimensions,
        },
        sort_keys=True,
    )
    fingerprint = digest(identity.encode())[:16]
    client = chromadb.PersistentClient(
        path=str(settings.data_dir / "chroma" / fingerprint),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return fingerprint, {
        name: client.get_or_create_collection(name, embedding_function=None)
        for name in ("game_meta", "rule_docs")
    }


async def index_bundle(settings, rows):
    fingerprint, collections = vector_collections(settings)
    provider = embedding_provider(settings)
    totals = {
        "embedded": 0,
        "cached": 0,
        "provider": settings.embedding_provider,
        "fingerprint": fingerprint,
    }

    async def upsert(collection, records):
        for offset in range(0, len(records), 24):
            batch = records[offset : offset + 24]
            existing = collection.get(ids=[r["id"] for r in batch], include=["metadatas"])
            hashes = {
                i: m.get("record_hash")
                for i, m in zip(existing["ids"], existing["metadatas"], strict=True)
            }
            pending = []
            for record in batch:
                h = digest(json.dumps(record, sort_keys=True).encode())
                record["metadata"]["record_hash"] = h
                if hashes.get(record["id"]) != h:
                    pending.append(record)
            totals["cached"] += len(batch) - len(pending)
            if not pending:
                continue
            vectors = await provider.embed([r["text"] for r in pending])
            collection.upsert(
                ids=[r["id"] for r in pending],
                embeddings=vectors,
                documents=[r["text"] for r in pending],
                metadatas=[r["metadata"] for r in pending],
            )
            totals["embedded"] += len(pending)

    for row in rows:
        await upsert(
            collections["game_meta"],
            [
                {
                    "id": row["slug"],
                    "text": json.dumps(row, ensure_ascii=False),
                    "metadata": {"game_id": row["slug"]},
                }
            ],
        )
        manifest = settings.data_dir / "manifests" / f"{row['slug']}.json"
        if not manifest.exists():
            raise ValueError("game_manifest_missing: " + row["slug"])
        sources = json.loads(manifest.read_text(encoding="utf-8"))
        if not sources:
            raise ValueError("game_has_no_documents: " + row["slug"])
        if any(source["status"] != "extracted" for source in sources):
            raise ValueError("game_has_failed_documents: " + row["slug"])
        records = []
        for source in sources:
            if source["status"] != "extracted":
                continue
            artifact = json.loads(
                (settings.data_dir / source["extracted_key"]).read_text(encoding="utf-8")
            )
            for chunk in artifact["chunks"]:
                records.append(
                    {
                        "id": digest((chunk["id"] + source["source_id"]).encode()),
                        "text": chunk["text"],
                        "metadata": {
                            "game_id": row["slug"],
                            "edition_id": source["edition_id"],
                            "document_id": source["document_id"],
                            "chunk_id": chunk["id"],
                            "page_start": chunk["page_start"],
                            "page_end": chunk["page_end"],
                            "locator": chunk["locator"],
                            "source_type": source["source_type"],
                            "source_url": source["source_url"] or "",
                            "document_type": source["document_type"] or "unknown",
                            **{k: chunk[k] for k in ("extraction_method", "review_note")
                               if k in chunk},
                        },
                    }
                )
        await upsert(collections["rule_docs"], records)
        # Remove stale chunks only after the replacement data is ready.
        old = collections["rule_docs"].get(where={"game_id": row["slug"]}, include=[])["ids"]
        stale = sorted(set(old) - {r["id"] for r in records})
        if stale:
            collections["rule_docs"].delete(ids=stale)
    totals["counts"] = {k: c.count() for k, c in collections.items()}
    save_json(settings.data_dir / "index-reports" / f"{fingerprint}.json", totals)
    return totals


async def index_catalog(settings, rows, progress=None):
    """Process every game, checkpointing failures without treating them as supported."""
    fingerprint, collections = vector_collections(settings)
    report = {"provider": settings.embedding_provider, "fingerprint": fingerprint, "games": []}
    path = settings.data_dir / "index-reports" / f"{fingerprint}-catalog.json"
    for row in rows:
        result = {"game_id": row["slug"]}
        try:
            totals = await index_bundle(settings, [row])
            result.update(status="indexed", embedded=totals["embedded"], cached=totals["cached"])
        except (ValueError, ProviderError, OSError) as exc:
            result.update(status="failed", error=str(exc))
        report["games"].append(result)
        report["counts"] = {name: collection.count() for name, collection in collections.items()}
        report["indexed_games"] = sum(r["status"] == "indexed" for r in report["games"])
        report["failed_games"] = len(report["games"]) - report["indexed_games"]
        save_json(path, report)
        if progress:
            progress(result)
    return report
