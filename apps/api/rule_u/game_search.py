"""Game discovery: semantic ranking, with hard constraints checked against SQLite."""

import re

from rule_u.ingestion import vector_collections
from rule_u.providers import ProviderError, embedding_provider


def constraints(body, categories):
    players = body.players
    minutes = body.max_minutes
    if players is None and (match := re.search(r"(\d+)\s*(?:명|인)(?!\s*(?:이상|이하|부터))", body.query)):
        players = int(match[1])
    if minutes is None and (match := re.search(r"(\d+)\s*분\s*(?:이내|이하|안|내)", body.query)):
        minutes = int(match[1])
    category = body.category or next((c for c in categories if c in body.query), "")
    return players, minutes, category


async def semantic_ids(settings, query):
    _, collections = vector_collections(settings)
    collection = collections["game_meta"]
    count = collection.count()
    if not count:
        raise ProviderError("search_index_missing")
    vector = (await embedding_provider(settings).embed([query]))[0]
    result = collection.query(query_embeddings=[vector], n_results=count, include=[])
    return result["ids"][0]
