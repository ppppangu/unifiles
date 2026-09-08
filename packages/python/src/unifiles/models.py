"""Public SDK models composed from generated protocol models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from typing import Any, Generic, TypeVar

from pydantic import PrivateAttr
from unifiles_generated.models.api_key_resource import APIKeyResource
from unifiles_generated.models.chunk_resource import ChunkResource
from unifiles_generated.models.deletion_result import DeletionResult
from unifiles_generated.models.document_resource import DocumentResource
from unifiles_generated.models.extraction_resource import ExtractionResource
from unifiles_generated.models.file_resource import FileResource
from unifiles_generated.models.health_details import HealthDetails
from unifiles_generated.models.health_status import HealthStatus
from unifiles_generated.models.knowledge_base_resource import KnowledgeBaseResource
from unifiles_generated.models.search_results import SearchResults
from unifiles_generated.models.supported_file_types import SupportedFileTypes
from unifiles_generated.models.usage_limits import UsageLimits
from unifiles_generated.models.usage_stats import UsageStats
from unifiles_generated.models.webhook_resource import WebhookResource

from .exceptions import ProcessingError, TimeoutError

APIKey = APIKeyResource
Chunk = ChunkResource
File = FileResource
KnowledgeBase = KnowledgeBaseResource
Webhook = WebhookResource

T = TypeVar("T")


class ListResponse(Generic[T]):
    """Iterable view over any generated concrete list model."""

    def __init__(self, generated: Any) -> None:
        self._generated = generated

    @property
    def items(self) -> list[T]:
        return self._generated.items

    @items.setter
    def items(self, value: list[T]) -> None:
        self._generated.items = value

    @property
    def total(self) -> int:
        return self._generated.total

    @property
    def limit(self) -> int:
        return self._generated.limit

    @property
    def offset(self) -> int:
        return self._generated.offset

    @property
    def has_more(self) -> bool:
        return self._generated.has_more

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> T:
        return self.items[index]

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return self._generated.model_dump(**kwargs)


class ExtractionJob(ExtractionResource):
    _waiter: Callable[[str, float, float], ExtractionJob] | None = PrivateAttr(default=None)

    def _bind_waiter(self, waiter: Callable[[str, float, float], ExtractionJob]) -> ExtractionJob:
        self._waiter = waiter
        return self

    def wait(self, timeout: float = 300, poll_interval: float = 2) -> ExtractionJob:
        if self._waiter is None:
            raise RuntimeError("ExtractionJob is not bound to a client")
        updated = self._waiter(self.id, timeout, poll_interval)
        _replace_model(self, updated)
        return self


class AsyncExtractionJob(ExtractionResource):
    _waiter: Callable[[str, float, float], Awaitable[AsyncExtractionJob]] | None = PrivateAttr(
        default=None
    )

    def _bind_waiter(
        self, waiter: Callable[[str, float, float], Awaitable[AsyncExtractionJob]]
    ) -> AsyncExtractionJob:
        self._waiter = waiter
        return self

    async def wait(self, timeout: float = 300, poll_interval: float = 2) -> AsyncExtractionJob:
        if self._waiter is None:
            raise RuntimeError("ExtractionJob is not bound to a client")
        updated = await self._waiter(self.id, timeout, poll_interval)
        _replace_model(self, updated)
        return self


class IndexedDocument(DocumentResource):
    _waiter: Callable[[str, str, float, float], IndexedDocument] | None = PrivateAttr(default=None)

    def _bind_waiter(self, waiter: Callable[[str, str, float, float], IndexedDocument]) -> IndexedDocument:
        self._waiter = waiter
        return self

    def wait(self, timeout: float = 300, poll_interval: float = 2) -> IndexedDocument:
        if self._waiter is None:
            raise RuntimeError("IndexedDocument is not bound to a client")
        updated = self._waiter(self.kb_id, self.id, timeout, poll_interval)
        _replace_model(self, updated)
        return self


class AsyncIndexedDocument(DocumentResource):
    _waiter: Callable[[str, str, float, float], Awaitable[AsyncIndexedDocument]] | None = PrivateAttr(
        default=None
    )

    def _bind_waiter(
        self, waiter: Callable[[str, str, float, float], Awaitable[AsyncIndexedDocument]]
    ) -> AsyncIndexedDocument:
        self._waiter = waiter
        return self

    async def wait(self, timeout: float = 300, poll_interval: float = 2) -> AsyncIndexedDocument:
        if self._waiter is None:
            raise RuntimeError("IndexedDocument is not bound to a client")
        updated = await self._waiter(self.kb_id, self.id, timeout, poll_interval)
        _replace_model(self, updated)
        return self


def _replace_model(target: Any, source: Any) -> None:
    for name in type(target).model_fields:
        setattr(target, name, getattr(source, name))


def raise_for_terminal_failure(resource: ExtractionResource | DocumentResource) -> None:
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
    "AsyncIndexedDocument",
    "AsyncExtractionJob",
    "Chunk",
    "DeletionResult",
    "IndexedDocument",
    "ExtractionJob",
    "File",
    "HealthDetails",
    "HealthStatus",
    "KnowledgeBase",
    "ListResponse",
    "SearchResults",
    "SupportedFileTypes",
    "UsageLimits",
    "UsageStats",
    "Webhook",
]
