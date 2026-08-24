from __future__ import annotations

import hashlib
import hmac
import io
import json
import math
import re
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from .store import Store, identifier, now

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
}


def dispatch_event(store: Store, user_id: str, event: str, data: dict[str, Any]) -> None:
    delivery_id = identifier("evt")
    payload = {"id": delivery_id, "type": event, "created_at": now(), "data": data}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    for webhook in store.matching_webhooks(user_id, event):
        signature = hmac.new(webhook["secret"].encode(), encoded, hashlib.sha256).hexdigest()
        try:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "X-Unifiles-Event": event,
                "X-Unifiles-Delivery": delivery_id,
                "X-Unifiles-Signature": f"sha256={signature}",
            }
            response = httpx.post(
                webhook["url"],
                content=encoded,
                headers=headers,
                timeout=10,
            )
            if response.is_success:
                store.mark_webhook_delivery(webhook["id"])
        except httpx.HTTPError:
            continue


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("The file could not be decoded as text")


def _remote_extract(
    store: Store,
    file: dict[str, Any],
    mode: str,
    options: dict[str, Any],
) -> tuple[str, int, dict[str, Any]]:
    endpoint = store.settings.ocr_endpoint
    if not endpoint:
        raise ValueError(
            f"No extractor is configured for {file['content_type']}; configure UNIFILES_OCR_ENDPOINT"
        )
    headers: dict[str, str] = {}
    if store.settings.ocr_api_key:
        headers["Authorization"] = f"Bearer {store.settings.ocr_api_key}"
    path = Path(file["storage_path"])
    response = httpx.post(
        endpoint,
        files={"file": (file["filename"], path.read_bytes(), file["content_type"])},
        data={"mode": mode, "options": json.dumps(options, ensure_ascii=False)},
        headers=headers,
        timeout=store.settings.ocr_timeout_seconds,
    )
    if response.is_error:
        raise ValueError(f"OCR provider returned HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as error:
        raise ValueError("OCR provider returned invalid JSON") from error
    if isinstance(body, dict) and body.get("success") is True:
        body = body.get("data")
    if not isinstance(body, dict) or not isinstance(body.get("markdown"), str):
        raise ValueError("OCR provider response must contain a markdown string")
    return (
        body["markdown"],
        int(body.get("total_pages", 1)),
        {"parser": "remote-ocr", **(body.get("metadata") or {})},
    )


def _extract(
    store: Store,
    file: dict[str, Any],
    mode: str,
    options: dict[str, Any],
) -> tuple[str, int, dict[str, Any]]:
    provider = str(options.get("ocr_provider", "default"))
    if mode == "advanced" or provider not in {"default", "builtin"}:
        return _remote_extract(store, file, mode, options)
    path = Path(file["storage_path"])
    content = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf" or file["content_type"] == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError("The PDF has no extractable text; configure an OCR provider")
        return text, len(pages), {"parser": "pypdf"}
    if suffix in TEXT_EXTENSIONS or file["content_type"].startswith("text/"):
        return _decode_text(content), 1, {"parser": "text"}
    return _remote_extract(store, file, mode, options)


def run_extraction(store: Store, user_id: str, extraction_id: str) -> None:
    extraction = store.extraction(user_id, extraction_id, internal=True)
    try:
        store.update_extraction(extraction_id, status="processing", progress=10)
        file = store.file(user_id, extraction["file_id"], internal=True)
        text, pages, metadata = _extract(
            store,
            file,
            extraction["mode"],
            extraction["options"],
        )
        markdown = (
            text
            if metadata.get("parser") == "remote-ocr"
            or file["filename"].lower().endswith((".md", ".markdown"))
            else f"# {file['filename']}\n\n{text}"
        )
        metadata.update({"mode": extraction["mode"], "options": extraction["options"]})
        store.update_extraction(
            extraction_id,
            status="completed",
            progress=100,
            markdown=markdown,
            total_pages=pages,
            metadata=metadata,
            completed_at=now(),
        )
        dispatch_event(
            store,
            user_id,
            "extraction.completed",
            {
                "extraction_id": extraction_id,
                "file_id": extraction["file_id"],
                "total_pages": pages,
            },
        )
    except Exception as error:
        failure = {"code": "EXTRACTION_FAILED", "message": str(error)}
        store.update_extraction(
            extraction_id,
            status="failed",
            progress=100,
            error=failure,
            completed_at=now(),
        )
        dispatch_event(
            store,
            user_id,
            "extraction.failed",
            {"extraction_id": extraction_id, "file_id": extraction["file_id"], "error": failure},
        )


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
