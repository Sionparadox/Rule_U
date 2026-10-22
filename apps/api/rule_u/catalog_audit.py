"""Read-only validation of local extraction artifacts and the selected vector index."""

import json
import math

from rule_u.ingestion import digest, vector_collections


def audit_catalog(settings, rows):
    fingerprint, collections = vector_collections(settings)
    games = []
    for row in rows:
        path = settings.data_dir / "manifests" / f"{row['slug']}.json"
        sources = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        expected = set()
        for source in sources:
            if source["status"] != "extracted":
                continue
            artifact = json.loads(
                (settings.data_dir / source["extracted_key"]).read_text(encoding="utf-8")
            )
            pages = {page["page"]: page["text"] for page in artifact["pages"]}
            for chunk in artifact["chunks"]:
                assert chunk["text"] == pages[chunk["page_start"]][chunk["start"] : chunk["end"]]
                assert chunk["page_start"] == chunk["page_end"]
                expected.add(digest((chunk["id"] + source["source_id"]).encode()))
        actual = collections["rule_docs"].get(
            where={"game_id": row["slug"]}, include=["embeddings", "metadatas"]
        )
        for vector in actual["embeddings"]:
            assert len(vector) == settings.embedding_dimensions
            assert all(math.isfinite(float(value)) for value in vector)
        complete = bool(sources) and all(s["status"] == "extracted" for s in sources)
        if complete:
            assert set(actual["ids"]) == expected
        games.append(
            {
                "game_id": row["slug"],
                "name": row["name_ko"],
                "status": "indexed" if complete else "needs_review",
                "documents": len(sources),
                "indexed_chunks": len(actual["ids"]),
                "failures": [
                    {"edition_id": s["edition_id"], "error": s.get("error")}
                    for s in sources
                    if s["status"] != "extracted"
                ],
            }
        )
    metadata = collections["game_meta"].get(ids=[row["slug"] for row in rows])
    assert len(metadata["ids"]) == len(rows)
    return {
        "fingerprint": fingerprint,
        "provider": settings.embedding_provider,
        "games": games,
        "game_count": len(rows),
        "indexed_games": sum(g["status"] == "indexed" for g in games),
        "needs_review_games": sum(g["status"] == "needs_review" for g in games),
        "indexed_chunks": sum(g["indexed_chunks"] for g in games),
    }
