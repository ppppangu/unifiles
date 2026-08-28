"""Document indexing use cases."""

from __future__ import annotations

import re

from ...shared.database import Store, identifier, now
from ..search.service import embedding
from ..webhooks.service import dispatch_event


def _split_markdown(markdown: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", markdown) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > chunk_size:
            chunks.append(current)
            prefix = current[-overlap:] if overlap > 0 else ""
            current = f"{prefix}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [markdown]


def run_indexing(store: Store, user_id: str, kb_id: str, document_id: str) -> None:
    document = store.document(user_id, kb_id, document_id, internal=True)
    try:
        store.update_document(document_id, status="indexing")
        extraction = store.extraction(user_id, document["extraction_id"])
        if extraction["status"] != "completed" or not extraction["markdown"]:
            raise ValueError("The associated extraction is not complete")
        kb = store.kb(user_id, kb_id)
        strategy = kb["chunking_strategy"]
        chunk_size = max(64, int(strategy.get("chunk_size", 512)))
        overlap = max(0, min(chunk_size // 2, int(strategy.get("overlap", 50))))
        contents = _split_markdown(extraction["markdown"], chunk_size, overlap)
        chunks = [
            {
                "id": identifier("chunk"),
                "position": position,
                "content": content,
                "vector": embedding(content),
                "metadata": {**(document.get("metadata") or {}), "position": position},
            }
            for position, content in enumerate(contents)
        ]
        store.replace_chunks(document, chunks)
        store.update_document(
            document_id,
            status="indexed",
            chunk_count=len(chunks),
            indexed_at=now(),
        )
        dispatch_event(
            store,
            user_id,
            "document.indexed",
            {"document_id": document_id, "kb_id": kb_id, "chunk_count": len(chunks)},
        )
    except Exception as error:
        failure = {"code": "INDEXING_FAILED", "message": str(error)}
        store.update_document(document_id, status="failed", error=failure)
        dispatch_event(
            store,
            user_id,
            "document.index_failed",
            {"document_id": document_id, "kb_id": kb_id, "error": failure},
        )
