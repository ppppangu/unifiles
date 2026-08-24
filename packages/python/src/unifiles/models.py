"""Typed public resource models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from .exceptions import ProcessingError, TimeoutError


class APIModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=True)


T = TypeVar("T")


class ListResponse(APIModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> T:
        return self.items[index]


class File(APIModel):
    id: str
    filename: str
    content_type: str
    size: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class ExtractionData(APIModel):
    id: str
    file_id: str
    status: str
    mode: str = "normal"
    progress: int | None = None
    markdown: str | None = None
    total_pages: int | None = None
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None

    def _replace_from(self, other: ExtractionData) -> None:
        for name in type(self).model_fields:
            setattr(self, name, getattr(other, name))


class Extraction(ExtractionData):
    _waiter: Callable[[str, float, float], Extraction] | None = PrivateAttr(default=None)

    def _bind_waiter(self, waiter: Callable[[str, float, float], Extraction]) -> Extraction:
        self._waiter = waiter
        return self

    def wait(self, timeout: float = 300, poll_interval: float = 2) -> Extraction:
        if self._waiter is None:
            raise RuntimeError("Extraction is not bound to a client")
        updated = self._waiter(self.id, timeout, poll_interval)
        self._replace_from(updated)
        return self


class AsyncExtraction(ExtractionData):
    _waiter: Callable[[str, float, float], Awaitable[AsyncExtraction]] | None = PrivateAttr(
        default=None
    )

    def _bind_waiter(
        self, waiter: Callable[[str, float, float], Awaitable[AsyncExtraction]]
    ) -> AsyncExtraction:
        self._waiter = waiter
        return self

    async def wait(self, timeout: float = 300, poll_interval: float = 2) -> AsyncExtraction:
        if self._waiter is None:
            raise RuntimeError("Extraction is not bound to a client")
        updated = await self._waiter(self.id, timeout, poll_interval)
        self._replace_from(updated)
        return self


class KnowledgeBase(APIModel):
    id: str
    name: str
    description: str | None = None
    chunking_strategy: dict[str, Any] = Field(default_factory=dict)
    document_count: int = 0
    chunk_count: int = 0
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DocumentData(APIModel):
    id: str
    kb_id: str
    file_id: str
    title: str | None = None
    status: str
    chunk_count: int = 0
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    indexed_at: datetime | None = None

    def _replace_from(self, other: DocumentData) -> None:
        for name in type(self).model_fields:
            setattr(self, name, getattr(other, name))


class Document(DocumentData):
    _waiter: Callable[[str, str, float, float], Document] | None = PrivateAttr(default=None)

    def _bind_waiter(self, waiter: Callable[[str, str, float, float], Document]) -> Document:
        self._waiter = waiter
        return self

    def wait(self, timeout: float = 300, poll_interval: float = 2) -> Document:
        if self._waiter is None:
            raise RuntimeError("Document is not bound to a client")
        updated = self._waiter(self.kb_id, self.id, timeout, poll_interval)
        self._replace_from(updated)
        return self


class AsyncDocument(DocumentData):
    _waiter: Callable[[str, str, float, float], Awaitable[AsyncDocument]] | None = PrivateAttr(
        default=None
    )

    def _bind_waiter(
        self, waiter: Callable[[str, str, float, float], Awaitable[AsyncDocument]]
    ) -> AsyncDocument:
        self._waiter = waiter
        return self

    async def wait(self, timeout: float = 300, poll_interval: float = 2) -> AsyncDocument:
        if self._waiter is None:
            raise RuntimeError("Document is not bound to a client")
        updated = await self._waiter(self.kb_id, self.id, timeout, poll_interval)
        self._replace_from(updated)
        return self


class Chunk(APIModel):
    id: str
    document_id: str
    document_title: str | None = None
    content: str
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResults(APIModel):
    query: str
    chunks: list[Chunk] = Field(default_factory=list)
    total: int = 0


class Webhook(APIModel):
    id: str
    url: str
    events: list[str]
    enabled: bool = True
    description: str | None = None
    last_delivery_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class APIKey(APIModel):
    id: str
    name: str
    key: str | None = None
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class StorageUsage(APIModel):
    used_bytes: int = 0
    limit_bytes: int = 0
    used_percentage: float = 0


class ExtractionUsage(APIModel):
    pages_used: int = 0
    pages_limit: int = 0
    reset_at: datetime | None = None


class KnowledgeBaseUsage(APIModel):
    used: int = 0
    limit: int = 0


class UsageStats(APIModel):
    storage: StorageUsage = Field(default_factory=StorageUsage)
    extraction: ExtractionUsage = Field(default_factory=ExtractionUsage)
    knowledge_bases: KnowledgeBaseUsage = Field(default_factory=KnowledgeBaseUsage)


class UsageLimits(APIModel):
    api_calls: dict[str, Any] = Field(default_factory=dict)
    storage: dict[str, Any] = Field(default_factory=dict)
    files: dict[str, Any] = Field(default_factory=dict)


class DeletionResult(APIModel):
    id: str
    deleted: bool = True


class SupportedFileTypes(APIModel):
    document_types: list[str] = Field(default_factory=list)
    image_types: list[str] = Field(default_factory=list)
    all_types: list[str] = Field(default_factory=list)


def raise_for_terminal_failure(resource: ExtractionData | DocumentData) -> None:
    if resource.status in {"failed", "cancelled"}:
        error = resource.error or {}
        raise ProcessingError(
            str(error.get("message", "Processing failed")),
            code=str(error.get("code", "PROCESSING_FAILED")),
            details=error,
        )


def raise_wait_timeout(resource_type: str, resource_id: str, timeout: float) -> None:
    raise TimeoutError(
        f"Timed out waiting for {resource_type} {resource_id} after {timeout:g} seconds",
        code="WAIT_TIMEOUT",
    )


__all__ = [
    "APIKey",
    "AsyncDocument",
    "AsyncExtraction",
    "Chunk",
    "DeletionResult",
    "Document",
    "Extraction",
    "ExtractionUsage",
    "File",
    "KnowledgeBase",
    "KnowledgeBaseUsage",
    "ListResponse",
    "SearchResults",
    "StorageUsage",
    "SupportedFileTypes",
    "UsageLimits",
    "UsageStats",
    "Webhook",
]
