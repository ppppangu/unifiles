"""Resource namespaces used by the synchronous and asynchronous clients."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

from ._transport import AsyncTransport, SyncTransport
from .models import (
    APIKey,
    AsyncDocument,
    AsyncExtraction,
    DeletionResult,
    Document,
    Extraction,
    File,
    KnowledgeBase,
    ListResponse,
    SearchResults,
    SupportedFileTypes,
    UsageLimits,
    UsageStats,
    Webhook,
    raise_for_terminal_failure,
    raise_wait_timeout,
)


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _idempotency_key() -> str:
    return str(uuid.uuid4())


def _upload_parts(
    path: str | Path | None,
    *,
    content: bytes | None,
    filename: str | None,
    content_type: str | None,
    metadata: dict[str, Any] | None,
    tags: list[str] | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if (path is None) == (content is None):
        raise ValueError("Provide exactly one of path or content")
    if path is not None:
        file_path = Path(path)
        content = file_path.read_bytes()
        filename = filename or file_path.name
    if not filename:
        raise ValueError("filename is required when uploading bytes")
    mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    files = {"file": (filename, content, mime)}
    form = {
        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        "tags": json.dumps(tags or [], ensure_ascii=False),
    }
    return files, form


class FilesResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def upload(
        self,
        path: str | Path | None = None,
        *,
        content: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> File:
        files, form = _upload_parts(
            path,
            content=content,
            filename=filename,
            content_type=content_type,
            metadata=metadata,
            tags=tags,
        )
        data = self._transport.request(
            "POST", "files", files=files, data=form, idempotency_key=_idempotency_key()
        )
        return File.model_validate(data)

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tags: list[str] | None = None,
        content_type: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> ListResponse[File]:
        data = self._transport.request(
            "GET",
            "files",
            params=_compact(
                {
                    "limit": limit,
                    "offset": offset,
                    "tags": ",".join(tags) if tags else None,
                    "content_type": content_type,
                    "sort_by": sort_by,
                    "order": order,
                }
            ),
        )
        return ListResponse[File].model_validate(data)

    def get(self, file_id: str) -> File:
        return File.model_validate(self._transport.request("GET", f"files/{file_id}"))

    def download(self, file_id: str) -> bytes:
        return self._transport.request_binary(f"files/{file_id}/download")

    def delete(self, file_id: str) -> DeletionResult:
        return DeletionResult.model_validate(self._transport.request("DELETE", f"files/{file_id}"))

    def list_supported_types(self) -> SupportedFileTypes:
        return SupportedFileTypes.model_validate(self._transport.request("GET", "files/types"))


class ExtractionsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def _bind(self, extraction: Extraction) -> Extraction:
        return extraction._bind_waiter(self._wait)

    def create(
        self,
        file_id: str,
        *,
        mode: str = "normal",
        options: dict[str, Any] | None = None,
    ) -> Extraction:
        data = self._transport.request(
            "POST",
            "extractions",
            json={"file_id": file_id, "mode": mode, "options": options or {}},
            idempotency_key=_idempotency_key(),
        )
        return self._bind(Extraction.model_validate(data))

    def get(self, extraction_id: str) -> Extraction:
        data = self._transport.request("GET", f"extractions/{extraction_id}")
        return self._bind(Extraction.model_validate(data))

    def list(self, file_id: str, *, limit: int = 50, offset: int = 0) -> ListResponse[Extraction]:
        data = self._transport.request(
            "GET", f"files/{file_id}/extractions", params={"limit": limit, "offset": offset}
        )
        result = ListResponse[Extraction].model_validate(data)
        result.items = [self._bind(item) for item in result.items]
        return result

    def _wait(self, extraction_id: str, timeout: float, poll_interval: float) -> Extraction:
        deadline = time.monotonic() + timeout
        while True:
            extraction = self.get(extraction_id)
            raise_for_terminal_failure(extraction)
            if extraction.status == "completed":
                return extraction
            if time.monotonic() >= deadline:
                raise_wait_timeout("extraction", extraction_id, timeout)
            time.sleep(poll_interval)


class DocumentsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def _bind(self, document: Document) -> Document:
        return document._bind_waiter(self._wait)

    def create(
        self,
        kb_id: str,
        file_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        data = self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/documents",
            json=_compact({"file_id": file_id, "title": title, "metadata": metadata}),
            idempotency_key=_idempotency_key(),
        )
        return self._bind(Document.model_validate(data))

    def list(self, kb_id: str, *, limit: int = 50, offset: int = 0) -> ListResponse[Document]:
        data = self._transport.request(
            "GET",
            f"knowledge-bases/{kb_id}/documents",
            params={"limit": limit, "offset": offset},
        )
        result = ListResponse[Document].model_validate(data)
        result.items = [self._bind(item) for item in result.items]
        return result

    def get(self, kb_id: str, document_id: str) -> Document:
        data = self._transport.request("GET", f"knowledge-bases/{kb_id}/documents/{document_id}")
        return self._bind(Document.model_validate(data))

    def delete(self, kb_id: str, document_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            self._transport.request("DELETE", f"knowledge-bases/{kb_id}/documents/{document_id}")
        )

    def _wait(self, kb_id: str, document_id: str, timeout: float, poll_interval: float) -> Document:
        deadline = time.monotonic() + timeout
        while True:
            document = self.get(kb_id, document_id)
            raise_for_terminal_failure(document)
            if document.status == "indexed":
                return document
            if time.monotonic() >= deadline:
                raise_wait_timeout("document", document_id, timeout)
            time.sleep(poll_interval)


class KnowledgeBasesResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport
        self.documents = DocumentsResource(transport)

    def create(
        self,
        name: str,
        *,
        description: str | None = None,
        chunking_strategy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeBase:
        data = self._transport.request(
            "POST",
            "knowledge-bases",
            json=_compact(
                {
                    "name": name,
                    "description": description,
                    "chunking_strategy": chunking_strategy,
                    "metadata": metadata,
                }
            ),
            idempotency_key=_idempotency_key(),
        )
        return KnowledgeBase.model_validate(data)

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[KnowledgeBase]:
        data = self._transport.request(
            "GET", "knowledge-bases", params={"limit": limit, "offset": offset}
        )
        return ListResponse[KnowledgeBase].model_validate(data)

    def get(self, kb_id: str) -> KnowledgeBase:
        return KnowledgeBase.model_validate(
            self._transport.request("GET", f"knowledge-bases/{kb_id}")
        )

    def update(self, kb_id: str, **changes: Any) -> KnowledgeBase:
        return KnowledgeBase.model_validate(
            self._transport.request("PATCH", f"knowledge-bases/{kb_id}", json=changes)
        )

    def delete(self, kb_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            self._transport.request("DELETE", f"knowledge-bases/{kb_id}")
        )

    def search(
        self,
        kb_id: str,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0,
        filter: dict[str, Any] | None = None,
    ) -> SearchResults:
        data = self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/search",
            json=_compact(
                {"query": query, "top_k": top_k, "threshold": threshold, "filter": filter}
            ),
            idempotency_key=_idempotency_key(),
        )
        return SearchResults.model_validate(data)

    def hybrid_search(
        self,
        kb_id: str,
        query: str,
        *,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = 5,
    ) -> SearchResults:
        data = self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/hybrid-search",
            json={
                "query": query,
                "vector_weight": vector_weight,
                "keyword_weight": keyword_weight,
                "top_k": top_k,
            },
            idempotency_key=_idempotency_key(),
        )
        return SearchResults.model_validate(data)


class WebhooksResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(self, url: str, events: list[str], *, description: str | None = None) -> Webhook:
        data = self._transport.request(
            "POST",
            "webhooks",
            json=_compact({"url": url, "events": events, "description": description}),
            idempotency_key=_idempotency_key(),
        )
        return Webhook.model_validate(data)

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[Webhook]:
        data = self._transport.request("GET", "webhooks", params={"limit": limit, "offset": offset})
        return ListResponse[Webhook].model_validate(data)

    def get(self, webhook_id: str) -> Webhook:
        return Webhook.model_validate(self._transport.request("GET", f"webhooks/{webhook_id}"))

    def update(self, webhook_id: str, **changes: Any) -> Webhook:
        return Webhook.model_validate(
            self._transport.request("PATCH", f"webhooks/{webhook_id}", json=changes)
        )

    def delete(self, webhook_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            self._transport.request("DELETE", f"webhooks/{webhook_id}")
        )


class APIKeysResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        name: str,
        *,
        scopes: list[str] | None = None,
        expires_at: str | None = None,
    ) -> APIKey:
        data = self._transport.request(
            "POST",
            "api-keys",
            json=_compact({"name": name, "scopes": scopes, "expires_at": expires_at}),
            idempotency_key=_idempotency_key(),
        )
        return APIKey.model_validate(data)

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[APIKey]:
        data = self._transport.request("GET", "api-keys", params={"limit": limit, "offset": offset})
        return ListResponse[APIKey].model_validate(data)

    def delete(self, key_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            self._transport.request("DELETE", f"api-keys/{key_id}")
        )

    revoke = delete


class UsageResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get_stats(self) -> UsageStats:
        return UsageStats.model_validate(self._transport.request("GET", "usage/stats"))

    def get_limits(self) -> UsageLimits:
        return UsageLimits.model_validate(self._transport.request("GET", "usage/limits"))


class AsyncFilesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def upload(
        self,
        path: str | Path | None = None,
        *,
        content: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> File:
        if path is not None:
            file_path = Path(path)
            content = await asyncio.to_thread(file_path.read_bytes)
            filename = filename or file_path.name
            path = None
        files, form = _upload_parts(
            path,
            content=content,
            filename=filename,
            content_type=content_type,
            metadata=metadata,
            tags=tags,
        )
        data = await self._transport.request(
            "POST", "files", files=files, data=form, idempotency_key=_idempotency_key()
        )
        return File.model_validate(data)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tags: list[str] | None = None,
        content_type: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> ListResponse[File]:
        query = {
            "limit": limit,
            "offset": offset,
            "tags": ",".join(tags) if tags else None,
            "content_type": content_type,
            "sort_by": sort_by,
            "order": order,
        }
        data = await self._transport.request("GET", "files", params=_compact(query))
        return ListResponse[File].model_validate(data)

    async def get(self, file_id: str) -> File:
        return File.model_validate(await self._transport.request("GET", f"files/{file_id}"))

    async def download(self, file_id: str) -> bytes:
        return await self._transport.request_binary(f"files/{file_id}/download")

    async def delete(self, file_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            await self._transport.request("DELETE", f"files/{file_id}")
        )

    async def list_supported_types(self) -> SupportedFileTypes:
        return SupportedFileTypes.model_validate(
            await self._transport.request("GET", "files/types")
        )


class AsyncExtractionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    def _bind(self, extraction: AsyncExtraction) -> AsyncExtraction:
        return extraction._bind_waiter(self._wait)

    async def create(
        self, file_id: str, *, mode: str = "normal", options: dict[str, Any] | None = None
    ) -> AsyncExtraction:
        data = await self._transport.request(
            "POST",
            "extractions",
            json={"file_id": file_id, "mode": mode, "options": options or {}},
            idempotency_key=_idempotency_key(),
        )
        return self._bind(AsyncExtraction.model_validate(data))

    async def get(self, extraction_id: str) -> AsyncExtraction:
        data = await self._transport.request("GET", f"extractions/{extraction_id}")
        return self._bind(AsyncExtraction.model_validate(data))

    async def list(
        self, file_id: str, *, limit: int = 50, offset: int = 0
    ) -> ListResponse[AsyncExtraction]:
        data = await self._transport.request(
            "GET", f"files/{file_id}/extractions", params={"limit": limit, "offset": offset}
        )
        result = ListResponse[AsyncExtraction].model_validate(data)
        result.items = [self._bind(item) for item in result.items]
        return result

    async def _wait(
        self, extraction_id: str, timeout: float, poll_interval: float
    ) -> AsyncExtraction:
        deadline = time.monotonic() + timeout
        while True:
            extraction = await self.get(extraction_id)
            raise_for_terminal_failure(extraction)
            if extraction.status == "completed":
                return extraction
            if time.monotonic() >= deadline:
                raise_wait_timeout("extraction", extraction_id, timeout)
            await asyncio.sleep(poll_interval)


class AsyncDocumentsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    def _bind(self, document: AsyncDocument) -> AsyncDocument:
        return document._bind_waiter(self._wait)

    async def create(
        self,
        kb_id: str,
        file_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncDocument:
        data = await self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/documents",
            json=_compact({"file_id": file_id, "title": title, "metadata": metadata}),
            idempotency_key=_idempotency_key(),
        )
        return self._bind(AsyncDocument.model_validate(data))

    async def list(
        self, kb_id: str, *, limit: int = 50, offset: int = 0
    ) -> ListResponse[AsyncDocument]:
        data = await self._transport.request(
            "GET",
            f"knowledge-bases/{kb_id}/documents",
            params={"limit": limit, "offset": offset},
        )
        result = ListResponse[AsyncDocument].model_validate(data)
        result.items = [self._bind(item) for item in result.items]
        return result

    async def get(self, kb_id: str, document_id: str) -> AsyncDocument:
        data = await self._transport.request(
            "GET", f"knowledge-bases/{kb_id}/documents/{document_id}"
        )
        return self._bind(AsyncDocument.model_validate(data))

    async def delete(self, kb_id: str, document_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            await self._transport.request(
                "DELETE", f"knowledge-bases/{kb_id}/documents/{document_id}"
            )
        )

    async def _wait(
        self, kb_id: str, document_id: str, timeout: float, poll_interval: float
    ) -> AsyncDocument:
        deadline = time.monotonic() + timeout
        while True:
            document = await self.get(kb_id, document_id)
            raise_for_terminal_failure(document)
            if document.status == "indexed":
                return document
            if time.monotonic() >= deadline:
                raise_wait_timeout("document", document_id, timeout)
            await asyncio.sleep(poll_interval)


class AsyncKnowledgeBasesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport
        self.documents = AsyncDocumentsResource(transport)

    async def create(self, name: str, **options: Any) -> KnowledgeBase:
        data = await self._transport.request(
            "POST",
            "knowledge-bases",
            json=_compact({"name": name, **options}),
            idempotency_key=_idempotency_key(),
        )
        return KnowledgeBase.model_validate(data)

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[KnowledgeBase]:
        data = await self._transport.request(
            "GET", "knowledge-bases", params={"limit": limit, "offset": offset}
        )
        return ListResponse[KnowledgeBase].model_validate(data)

    async def get(self, kb_id: str) -> KnowledgeBase:
        return KnowledgeBase.model_validate(
            await self._transport.request("GET", f"knowledge-bases/{kb_id}")
        )

    async def update(self, kb_id: str, **changes: Any) -> KnowledgeBase:
        return KnowledgeBase.model_validate(
            await self._transport.request("PATCH", f"knowledge-bases/{kb_id}", json=changes)
        )

    async def delete(self, kb_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            await self._transport.request("DELETE", f"knowledge-bases/{kb_id}")
        )

    async def search(self, kb_id: str, query: str, **options: Any) -> SearchResults:
        data = await self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/search",
            json={"query": query, **options},
            idempotency_key=_idempotency_key(),
        )
        return SearchResults.model_validate(data)

    async def hybrid_search(self, kb_id: str, query: str, **options: Any) -> SearchResults:
        data = await self._transport.request(
            "POST",
            f"knowledge-bases/{kb_id}/hybrid-search",
            json={"query": query, **options},
            idempotency_key=_idempotency_key(),
        )
        return SearchResults.model_validate(data)


class AsyncWebhooksResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self, url: str, events: list[str], *, description: str | None = None
    ) -> Webhook:
        data = await self._transport.request(
            "POST",
            "webhooks",
            json=_compact({"url": url, "events": events, "description": description}),
            idempotency_key=_idempotency_key(),
        )
        return Webhook.model_validate(data)

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[Webhook]:
        data = await self._transport.request(
            "GET", "webhooks", params={"limit": limit, "offset": offset}
        )
        return ListResponse[Webhook].model_validate(data)

    async def get(self, webhook_id: str) -> Webhook:
        return Webhook.model_validate(
            await self._transport.request("GET", f"webhooks/{webhook_id}")
        )

    async def update(self, webhook_id: str, **changes: Any) -> Webhook:
        return Webhook.model_validate(
            await self._transport.request("PATCH", f"webhooks/{webhook_id}", json=changes)
        )

    async def delete(self, webhook_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            await self._transport.request("DELETE", f"webhooks/{webhook_id}")
        )


class AsyncAPIKeysResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(self, name: str, **options: Any) -> APIKey:
        data = await self._transport.request(
            "POST",
            "api-keys",
            json=_compact({"name": name, **options}),
            idempotency_key=_idempotency_key(),
        )
        return APIKey.model_validate(data)

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[APIKey]:
        data = await self._transport.request(
            "GET", "api-keys", params={"limit": limit, "offset": offset}
        )
        return ListResponse[APIKey].model_validate(data)

    async def delete(self, key_id: str) -> DeletionResult:
        return DeletionResult.model_validate(
            await self._transport.request("DELETE", f"api-keys/{key_id}")
        )

    revoke = delete


class AsyncUsageResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get_stats(self) -> UsageStats:
        return UsageStats.model_validate(await self._transport.request("GET", "usage/stats"))

    async def get_limits(self) -> UsageLimits:
        return UsageLimits.model_validate(await self._transport.request("GET", "usage/limits"))


__all__ = [
    "APIKeysResource",
    "AsyncAPIKeysResource",
    "AsyncExtractionsResource",
    "AsyncFilesResource",
    "AsyncKnowledgeBasesResource",
    "AsyncUsageResource",
    "AsyncWebhooksResource",
    "ExtractionsResource",
    "FilesResource",
    "KnowledgeBasesResource",
    "UsageResource",
    "WebhooksResource",
]
