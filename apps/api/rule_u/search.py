"""Search modes over one scoped chunk set: vector, keyword(BM25)+vector RRF, and MMR."""

import math
import re
from collections import Counter

from rule_u.discovery import normalize

RRF_K = 60
MMR_LAMBDA = 0.5


def tokens(text):
    # Korean has no reliable whitespace morphology here; bigrams catch particles/compounds.
    words = re.findall(r"\w+", normalize(text))
    result = []
    for word in words:
        result.append(word)
        if len(word) > 2 and re.search(r"[가-힣]", word):
            result.extend(word[i:i + 2] for i in range(len(word) - 1))
    return result


def bm25_ranking(query, documents, k1=1.2, b=0.75):
    """Return document indexes ordered by BM25, excluding zero-score documents."""
    terms = set(tokens(query))
    bags = [Counter(tokens(text)) for text in documents]
    if not terms or not bags:
        return []
    average = sum(sum(bag.values()) for bag in bags) / len(bags) or 1
    frequency = {t: sum(t in bag for bag in bags) for t in terms}
    scores = []
    for index, bag in enumerate(bags):
        length = sum(bag.values())
        score = 0.0
        for term in terms:
            if not bag[term]:
                continue
            idf = math.log(1 + (len(bags) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            tf = bag[term]
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average))
        if score > 0:
            scores.append((score, index))
    return [i for _, i in sorted(scores, key=lambda x: (-x[0], x[1]))]


def rrf(rankings, k=RRF_K):
    scores = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def mmr(query_vector, vectors, top_k, weight=MMR_LAMBDA):
    relevance = [cosine(query_vector, v) for v in vectors]
    chosen, remaining = [], list(range(len(vectors)))
    while remaining and len(chosen) < top_k:
        def score(i):
            redundancy = max((cosine(vectors[i], vectors[j]) for j in chosen), default=0.0)
            return weight * relevance[i] - (1 - weight) * redundancy
        best = max(remaining, key=lambda i: (score(i), -i))
        chosen.append(best)
        remaining.remove(best)
    return chosen


def search(collection, vector, query, where, mode, top_k, candidate_k):
    """Return [(metadata, text)] in rank order. Every mode reads the same filtered chunks."""
    if mode not in ("similarity", "hybrid", "mmr"):
        raise ValueError("unknown_search_mode")
    include = ["documents", "metadatas"] + (["embeddings"] if mode == "mmr" else [])
    found = collection.query(query_embeddings=[vector], n_results=candidate_k, where=where,
                             include=include)
    ids = found["ids"][0]
    rows = {i: (m, t) for i, m, t in zip(ids, found["metadatas"][0], found["documents"][0],
                                         strict=True)}
    if mode == "similarity":
        ranked = ids
    elif mode == "mmr":
        ranked = [ids[i] for i in mmr(vector, list(found["embeddings"][0]), top_k)]
    else:
        scoped = collection.get(where=where, include=["documents", "metadatas"])
        rows.update({i: (m, t) for i, m, t in zip(scoped["ids"], scoped["metadatas"],
                                                  scoped["documents"], strict=True)})
        keyword = [scoped["ids"][i] for i in bm25_ranking(query, scoped["documents"])]
        ranked = rrf([ids, keyword[:candidate_k]])
    return [rows[i] for i in ranked]
