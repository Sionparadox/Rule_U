"""Verify live-index idempotency with external embedding calls explicitly blocked."""

import asyncio
from pathlib import Path

from rule_u import ingestion
from rule_u.catalog_audit import audit_catalog
from rule_u.config import Settings
from rule_u.ingestion import load_catalog, save_json


class BlockedProvider:
    async def embed(self, texts):
        raise AssertionError("unexpected_external_embedding")


settings = Settings()
root = Path(__file__).resolve().parents[3]
rows = load_catalog(root.parent / "data/games")
ingestion.embedding_provider = lambda settings: BlockedProvider()
result = asyncio.run(ingestion.index_catalog(settings, rows))
assert result["failed_games"] == 0
assert sum(g["embedded"] for g in result["games"]) == 0
save_json(settings.data_dir / "stage2-idempotency.json", result)
audit = audit_catalog(settings, rows)
save_json(settings.data_dir / "stage2-audit.json", audit)
print({"indexed": audit["indexed_games"], "chunks": audit["indexed_chunks"], "new_embeddings": 0})
