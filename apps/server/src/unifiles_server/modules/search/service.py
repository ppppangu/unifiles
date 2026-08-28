"""Knowledge-base search scoring and retrieval service."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from ...shared.database import Store


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for part in re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]+", text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", part):
            tokens.extend(part)
            tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
        else:
            tokens.append(part)
    return tokens


def embedding(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode(), digest_size=16).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return max(0.0, sum(a * b for a, b in zip(left, right, strict=False)))


def _keyword_score(query: str, content: str) -> float:
    query_tokens = set(_tokens(query))
    content_tokens = set(_tokens(content))
    if not query_tokens:
        return 0.0
    return len(query_tokens & content_tokens) / len(query_tokens)


def search(
    store: Store,
    user_id: str,
    kb_id: str,
    query: str,
    *,
    top_k: int,
    threshold: float = 0,
    vector_weight: float = 1,
    keyword_weight: float = 0,
    metadata_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_vector = embedding(query)
    total_weight = vector_weight + keyword_weight
    vector_weight /= total_weight
    keyword_weight /= total_weight
    normalized_filter = {
        key.removeprefix("metadata."): value for key, value in (metadata_filter or {}).items()
    }
    matches: list[dict[str, Any]] = []
    for chunk in store.chunks(user_id, kb_id):
        if normalized_filter and any(
            chunk["metadata"].get(key) != value for key, value in normalized_filter.items()
        ):
            continue
        vector_score = _cosine(query_vector, chunk["vector"])
        keyword_score = _keyword_score(query, chunk["content"])
        score = vector_weight * vector_score + keyword_weight * keyword_score
        if score < threshold:
            continue
        matches.append(
            {
                "id": chunk["id"],
                "document_id": chunk["document_id"],
                "document_title": chunk["document_title"],
                "content": chunk["content"],
                "score": round(score, 6),
                "vector_score": round(vector_score, 6),
                "keyword_score": round(keyword_score, 6),
                "metadata": chunk["metadata"],
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    selected = matches[:top_k]
    return {"query": query, "chunks": selected, "total": len(selected)}
