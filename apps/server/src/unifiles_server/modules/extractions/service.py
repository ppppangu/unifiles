"""Content extraction use cases and provider adapters."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from ...shared.database import Store, now
from ..webhooks.service import dispatch_event

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
