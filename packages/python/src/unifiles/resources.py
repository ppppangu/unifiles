"""Ergonomic resource facades over the generated Python SDK core."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

from unifiles_generated.models.api_key_create import APIKeyCreate
from unifiles_generated.models.chunking_strategy import ChunkingStrategy
from unifiles_generated.models.document_create import DocumentCreate
from unifiles_generated.models.extraction_create import ExtractionCreate
from unifiles_generated.models.extraction_options import ExtractionOptions
from unifiles_generated.models.hybrid_search_request import HybridSearchRequest
from unifiles_generated.models.knowledge_base_create import KnowledgeBaseCreate
from unifiles_generated.models.knowledge_base_update import KnowledgeBaseUpdate
from unifiles_generated.models.search_request import SearchRequest
from unifiles_generated.models.webhook_create import WebhookCreate
from unifiles_generated.models.webhook_update import WebhookUpdate

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


def _idempotency_key() -> str:
    return str(uuid.uuid4())


def _upload(
    path: str | Path | None,
    *,
    content: bytes | None,
    filename: str | None,
) -> tuple[str, bytes]:
    if (path is None) == (content is None):
        raise ValueError("Provide exactly one of path or content")
    if path is not None:
        file_path = Path(path)
        content = file_path.read_bytes()
        filename = filename or file_path.name
    if not filename or content is None:
        raise ValueError("filename is required when uploading bytes")
    return filename, content


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
        upload = _upload(path, content=content, filename=filename)
        if content_type and (suffix := Path(upload[0]).suffix):
            mimetypes.add_type(content_type, suffix)
        response = self._transport.call_sync(
            self._transport.apis.files.upload_file_sync,
            retry_allowed=True,
            file=upload,
            idempotency_key=_idempotency_key(),
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
            tags=json.dumps(tags or [], ensure_ascii=False),
        )
        return response.data

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
        response = self._transport.call_sync(
            self._transport.apis.files.list_files_sync,
            retry_allowed=True,
            limit=limit,
            offset=offset,
            tags=",".join(tags) if tags else None,
            content_type=content_type,
            sort_by=sort_by,
            order=order,
        )
        return ListResponse(response.data)

    def get(self, file_id: str) -> File:
        response = self._transport.call_sync(
            self._transport.apis.files.get_file_sync,
            retry_allowed=True,
            file_id=file_id,
        )
        return response.data

    def download(self, file_id: str) -> bytes:
        return self._transport.call_sync(
            self._transport.apis.files.download_file_sync,
            retry_allowed=True,
            file_id=file_id,
        )

    def delete(self, file_id: str) -> DeletionResult:
        response = self._transport.call_sync(
            self._transport.apis.files.delete_file_sync,
            retry_allowed=True,
            file_id=file_id,
        )
        return response.data

    def list_supported_types(self) -> SupportedFileTypes:
        response = self._transport.call_sync(
            self._transport.apis.files.list_supported_file_types_sync,
            retry_allowed=True,
        )
        return response.data


class ExtractionsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def _bind(self, value: Any) -> Extraction:
        return Extraction.model_validate(value.model_dump())._bind_waiter(self._wait)

    def create(
        self,
        file_id: str,
        *,
        mode: str = "normal",
        options: dict[str, Any] | None = None,
    ) -> Extraction:
        payload = ExtractionCreate(
            file_id=file_id,
            mode=mode,
            options=ExtractionOptions.from_dict(options or {}),
        )
        response = self._transport.call_sync(
            self._transport.apis.extractions.create_extraction_sync,
            retry_allowed=True,
            extraction_create=payload,
            idempotency_key=_idempotency_key(),
        )
        return self._bind(response.data)

    def get(self, extraction_id: str) -> Extraction:
        response = self._transport.call_sync(
            self._transport.apis.extractions.get_extraction_sync,
            retry_allowed=True,
            extraction_id=extraction_id,
        )
        return self._bind(response.data)

    def list(self, file_id: str, *, limit: int = 50, offset: int = 0) -> ListResponse[Extraction]:
        response = self._transport.call_sync(
            self._transport.apis.extractions.list_file_extractions_sync,
            retry_allowed=True,
            file_id=file_id,
            limit=limit,
            offset=offset,
        )
        result: ListResponse[Extraction] = ListResponse(response.data)
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

    def _bind(self, value: Any) -> Document:
        return Document.model_validate(value.model_dump())._bind_waiter(self._wait)

    def create(
        self,
        kb_id: str,
        file_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        response = self._transport.call_sync(
            self._transport.apis.documents.create_document_sync,
            retry_allowed=True,
            kb_id=kb_id,
            document_create=DocumentCreate(
                file_id=file_id,
                title=title,
                metadata=metadata,
            ),
            idempotency_key=_idempotency_key(),
        )
        return self._bind(response.data)

    def list(self, kb_id: str, *, limit: int = 50, offset: int = 0) -> ListResponse[Document]:
        response = self._transport.call_sync(
            self._transport.apis.documents.list_documents_sync,
            retry_allowed=True,
            kb_id=kb_id,
            limit=limit,
            offset=offset,
        )
        result: ListResponse[Document] = ListResponse(response.data)
        result.items = [self._bind(item) for item in result.items]
        return result

    def get(self, kb_id: str, document_id: str) -> Document:
        response = self._transport.call_sync(
            self._transport.apis.documents.get_document_sync,
            retry_allowed=True,
            kb_id=kb_id,
            document_id=document_id,
        )
        return self._bind(response.data)

    def delete(self, kb_id: str, document_id: str) -> DeletionResult:
        response = self._transport.call_sync(
            self._transport.apis.documents.delete_document_sync,
            retry_allowed=True,
            kb_id=kb_id,
            document_id=document_id,
        )
        return response.data

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
        response = self._transport.call_sync(
            self._transport.apis.knowledge_bases.create_knowledge_base_sync,
            retry_allowed=True,
            knowledge_base_create=KnowledgeBaseCreate(
                name=name,
                description=description,
                chunking_strategy=(
                    ChunkingStrategy.from_dict(chunking_strategy)
                    if chunking_strategy is not None
                    else None
                ),
                metadata=metadata,
            ),
            idempotency_key=_idempotency_key(),
        )
        return response.data

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[KnowledgeBase]:
        response = self._transport.call_sync(
            self._transport.apis.knowledge_bases.list_knowledge_bases_sync,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    def get(self, kb_id: str) -> KnowledgeBase:
        response = self._transport.call_sync(
            self._transport.apis.knowledge_bases.get_knowledge_base_sync,
            retry_allowed=True,
            kb_id=kb_id,
        )
        return response.data

    def update(self, kb_id: str, **changes: Any) -> KnowledgeBase:
        response = self._transport.call_sync(
            self._transport.apis.knowledge_bases.update_knowledge_base_sync,
            kb_id=kb_id,
            knowledge_base_update=KnowledgeBaseUpdate.from_dict(changes),
        )
        return response.data

    def delete(self, kb_id: str) -> DeletionResult:
        response = self._transport.call_sync(
            self._transport.apis.knowledge_bases.delete_knowledge_base_sync,
            retry_allowed=True,
            kb_id=kb_id,
        )
        return response.data

    def search(
        self,
        kb_id: str,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0,
        filter: dict[str, Any] | None = None,
    ) -> SearchResults:
        response = self._transport.call_sync(
            self._transport.apis.search.search_knowledge_base_sync,
            kb_id=kb_id,
            search_request=SearchRequest(
                query=query,
                top_k=top_k,
                threshold=threshold,
                filter=filter,
            ),
        )
        return response.data

    def hybrid_search(
        self,
        kb_id: str,
        query: str,
        *,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = 5,
    ) -> SearchResults:
        response = self._transport.call_sync(
            self._transport.apis.search.hybrid_search_knowledge_base_sync,
            kb_id=kb_id,
            hybrid_search_request=HybridSearchRequest(
                query=query,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                top_k=top_k,
            ),
        )
        return response.data


class WebhooksResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(self, url: str, events: list[str], *, description: str | None = None) -> Webhook:
        response = self._transport.call_sync(
            self._transport.apis.webhooks.create_webhook_sync,
            retry_allowed=True,
            webhook_create=WebhookCreate(url=url, events=events, description=description),
            idempotency_key=_idempotency_key(),
        )
        return response.data

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[Webhook]:
        response = self._transport.call_sync(
            self._transport.apis.webhooks.list_webhooks_sync,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    def get(self, webhook_id: str) -> Webhook:
        response = self._transport.call_sync(
            self._transport.apis.webhooks.get_webhook_sync,
            retry_allowed=True,
            webhook_id=webhook_id,
        )
        return response.data

    def update(self, webhook_id: str, **changes: Any) -> Webhook:
        response = self._transport.call_sync(
            self._transport.apis.webhooks.update_webhook_sync,
            webhook_id=webhook_id,
            webhook_update=WebhookUpdate.from_dict(changes),
        )
        return response.data

    def delete(self, webhook_id: str) -> DeletionResult:
        response = self._transport.call_sync(
            self._transport.apis.webhooks.delete_webhook_sync,
            retry_allowed=True,
            webhook_id=webhook_id,
        )
        return response.data


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
        response = self._transport.call_sync(
            self._transport.apis.api_keys.create_api_key_sync,
            retry_allowed=True,
            api_key_create=APIKeyCreate.from_dict(
                {"name": name, "scopes": scopes, "expires_at": expires_at}
            ),
            idempotency_key=_idempotency_key(),
        )
        return response.data

    def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[APIKey]:
        response = self._transport.call_sync(
            self._transport.apis.api_keys.list_api_keys_sync,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    def delete(self, key_id: str) -> DeletionResult:
        response = self._transport.call_sync(
            self._transport.apis.api_keys.revoke_api_key_sync,
            retry_allowed=True,
            key_id=key_id,
        )
        return response.data

    revoke = delete


class UsageResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get_stats(self) -> UsageStats:
        return self._transport.call_sync(
            self._transport.apis.usage.get_usage_stats_sync,
            retry_allowed=True,
        ).data

    def get_limits(self) -> UsageLimits:
        return self._transport.call_sync(
            self._transport.apis.usage.get_usage_limits_sync,
            retry_allowed=True,
        ).data


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
        upload = _upload(path, content=content, filename=filename)
        if content_type and (suffix := Path(upload[0]).suffix):
            mimetypes.add_type(content_type, suffix)
        response = await self._transport.call_async(
            self._transport.apis.files.upload_file,
            retry_allowed=True,
            file=upload,
            idempotency_key=_idempotency_key(),
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
            tags=json.dumps(tags or [], ensure_ascii=False),
        )
        return response.data

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
        response = await self._transport.call_async(
            self._transport.apis.files.list_files,
            retry_allowed=True,
            limit=limit,
            offset=offset,
            tags=",".join(tags) if tags else None,
            content_type=content_type,
            sort_by=sort_by,
            order=order,
        )
        return ListResponse(response.data)

    async def get(self, file_id: str) -> File:
        return (
            await self._transport.call_async(
                self._transport.apis.files.get_file,
                retry_allowed=True,
                file_id=file_id,
            )
        ).data

    async def download(self, file_id: str) -> bytes:
        return await self._transport.call_async(
            self._transport.apis.files.download_file,
            retry_allowed=True,
            file_id=file_id,
        )

    async def delete(self, file_id: str) -> DeletionResult:
        return (
            await self._transport.call_async(
                self._transport.apis.files.delete_file,
                retry_allowed=True,
                file_id=file_id,
            )
        ).data

    async def list_supported_types(self) -> SupportedFileTypes:
        return (
            await self._transport.call_async(
                self._transport.apis.files.list_supported_file_types,
                retry_allowed=True,
            )
        ).data


class AsyncExtractionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    def _bind(self, value: Any) -> AsyncExtraction:
        return AsyncExtraction.model_validate(value.model_dump())._bind_waiter(self._wait)

    async def create(
        self, file_id: str, *, mode: str = "normal", options: dict[str, Any] | None = None
    ) -> AsyncExtraction:
        response = await self._transport.call_async(
            self._transport.apis.extractions.create_extraction,
            retry_allowed=True,
            extraction_create=ExtractionCreate(
                file_id=file_id,
                mode=mode,
                options=ExtractionOptions.from_dict(options or {}),
            ),
            idempotency_key=_idempotency_key(),
        )
        return self._bind(response.data)

    async def get(self, extraction_id: str) -> AsyncExtraction:
        response = await self._transport.call_async(
            self._transport.apis.extractions.get_extraction,
            retry_allowed=True,
            extraction_id=extraction_id,
        )
        return self._bind(response.data)

    async def list(
        self, file_id: str, *, limit: int = 50, offset: int = 0
    ) -> ListResponse[AsyncExtraction]:
        response = await self._transport.call_async(
            self._transport.apis.extractions.list_file_extractions,
            retry_allowed=True,
            file_id=file_id,
            limit=limit,
            offset=offset,
        )
        result: ListResponse[AsyncExtraction] = ListResponse(response.data)
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

    def _bind(self, value: Any) -> AsyncDocument:
        return AsyncDocument.model_validate(value.model_dump())._bind_waiter(self._wait)

    async def create(
        self,
        kb_id: str,
        file_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncDocument:
        response = await self._transport.call_async(
            self._transport.apis.documents.create_document,
            retry_allowed=True,
            kb_id=kb_id,
            document_create=DocumentCreate(
                file_id=file_id,
                title=title,
                metadata=metadata,
            ),
            idempotency_key=_idempotency_key(),
        )
        return self._bind(response.data)

    async def list(
        self, kb_id: str, *, limit: int = 50, offset: int = 0
    ) -> ListResponse[AsyncDocument]:
        response = await self._transport.call_async(
            self._transport.apis.documents.list_documents,
            retry_allowed=True,
            kb_id=kb_id,
            limit=limit,
            offset=offset,
        )
        result: ListResponse[AsyncDocument] = ListResponse(response.data)
        result.items = [self._bind(item) for item in result.items]
        return result

    async def get(self, kb_id: str, document_id: str) -> AsyncDocument:
        response = await self._transport.call_async(
            self._transport.apis.documents.get_document,
            retry_allowed=True,
            kb_id=kb_id,
            document_id=document_id,
        )
        return self._bind(response.data)

    async def delete(self, kb_id: str, document_id: str) -> DeletionResult:
        return (
            await self._transport.call_async(
                self._transport.apis.documents.delete_document,
                retry_allowed=True,
                kb_id=kb_id,
                document_id=document_id,
            )
        ).data

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
        strategy = options.pop("chunking_strategy", None)
        response = await self._transport.call_async(
            self._transport.apis.knowledge_bases.create_knowledge_base,
            retry_allowed=True,
            knowledge_base_create=KnowledgeBaseCreate(
                name=name,
                chunking_strategy=(ChunkingStrategy.from_dict(strategy) if strategy else None),
                **options,
            ),
            idempotency_key=_idempotency_key(),
        )
        return response.data

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[KnowledgeBase]:
        response = await self._transport.call_async(
            self._transport.apis.knowledge_bases.list_knowledge_bases,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    async def get(self, kb_id: str) -> KnowledgeBase:
        return (
            await self._transport.call_async(
                self._transport.apis.knowledge_bases.get_knowledge_base,
                retry_allowed=True,
                kb_id=kb_id,
            )
        ).data

    async def update(self, kb_id: str, **changes: Any) -> KnowledgeBase:
        return (
            await self._transport.call_async(
                self._transport.apis.knowledge_bases.update_knowledge_base,
                kb_id=kb_id,
                knowledge_base_update=KnowledgeBaseUpdate.from_dict(changes),
            )
        ).data

    async def delete(self, kb_id: str) -> DeletionResult:
        return (
            await self._transport.call_async(
                self._transport.apis.knowledge_bases.delete_knowledge_base,
                retry_allowed=True,
                kb_id=kb_id,
            )
        ).data

    async def search(self, kb_id: str, query: str, **options: Any) -> SearchResults:
        return (
            await self._transport.call_async(
                self._transport.apis.search.search_knowledge_base,
                kb_id=kb_id,
                search_request=SearchRequest(query=query, **options),
            )
        ).data

    async def hybrid_search(self, kb_id: str, query: str, **options: Any) -> SearchResults:
        return (
            await self._transport.call_async(
                self._transport.apis.search.hybrid_search_knowledge_base,
                kb_id=kb_id,
                hybrid_search_request=HybridSearchRequest(query=query, **options),
            )
        ).data


class AsyncWebhooksResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self, url: str, events: list[str], *, description: str | None = None
    ) -> Webhook:
        return (
            await self._transport.call_async(
                self._transport.apis.webhooks.create_webhook,
                retry_allowed=True,
                webhook_create=WebhookCreate(url=url, events=events, description=description),
                idempotency_key=_idempotency_key(),
            )
        ).data

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[Webhook]:
        response = await self._transport.call_async(
            self._transport.apis.webhooks.list_webhooks,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    async def get(self, webhook_id: str) -> Webhook:
        return (
            await self._transport.call_async(
                self._transport.apis.webhooks.get_webhook,
                retry_allowed=True,
                webhook_id=webhook_id,
            )
        ).data

    async def update(self, webhook_id: str, **changes: Any) -> Webhook:
        return (
            await self._transport.call_async(
                self._transport.apis.webhooks.update_webhook,
                webhook_id=webhook_id,
                webhook_update=WebhookUpdate.from_dict(changes),
            )
        ).data

    async def delete(self, webhook_id: str) -> DeletionResult:
        return (
            await self._transport.call_async(
                self._transport.apis.webhooks.delete_webhook,
                retry_allowed=True,
                webhook_id=webhook_id,
            )
        ).data


class AsyncAPIKeysResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(self, name: str, **options: Any) -> APIKey:
        return (
            await self._transport.call_async(
                self._transport.apis.api_keys.create_api_key,
                retry_allowed=True,
                api_key_create=APIKeyCreate.from_dict({"name": name, **options}),
                idempotency_key=_idempotency_key(),
            )
        ).data

    async def list(self, *, limit: int = 50, offset: int = 0) -> ListResponse[APIKey]:
        response = await self._transport.call_async(
            self._transport.apis.api_keys.list_api_keys,
            retry_allowed=True,
            limit=limit,
            offset=offset,
        )
        return ListResponse(response.data)

    async def delete(self, key_id: str) -> DeletionResult:
        return (
            await self._transport.call_async(
                self._transport.apis.api_keys.revoke_api_key,
                retry_allowed=True,
                key_id=key_id,
            )
        ).data

    revoke = delete


class AsyncUsageResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get_stats(self) -> UsageStats:
        return (
            await self._transport.call_async(
                self._transport.apis.usage.get_usage_stats,
                retry_allowed=True,
            )
        ).data

    async def get_limits(self) -> UsageLimits:
        return (
            await self._transport.call_async(
                self._transport.apis.usage.get_usage_limits,
                retry_allowed=True,
            )
        ).data


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
