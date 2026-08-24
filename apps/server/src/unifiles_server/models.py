from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FileResource(Model):
    id: str
    filename: str
    content_type: str
    size: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class ExtractionCreate(Model):
    file_id: str
    mode: Literal["simple", "normal", "advanced"] = "normal"
    options: dict[str, Any] = Field(default_factory=dict)


class ExtractionResource(Model):
    id: str
    file_id: str
    status: Literal["pending", "processing", "completed", "failed", "cancelled"]
    mode: str
    progress: int | None = None
    markdown: str | None = None
    total_pages: int | None = None
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class KnowledgeBaseCreate(Model):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    chunking_strategy: dict[str, Any] = Field(
        default_factory=lambda: {"type": "semantic", "chunk_size": 512, "overlap": 50}
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunking_strategy")
    @classmethod
    def valid_chunking_strategy(cls, value: dict[str, Any]) -> dict[str, Any]:
        strategy = value.get("type", "semantic")
        if strategy not in {"fixed", "semantic", "hierarchical", "paragraph"}:
            raise ValueError("Unsupported chunking strategy")
        chunk_size = int(value.get("chunk_size", 512))
        overlap = int(value.get("overlap", 50))
        if chunk_size < 64 or chunk_size > 100_000:
            raise ValueError("chunk_size must be between 64 and 100000")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        return {**value, "type": strategy, "chunk_size": chunk_size, "overlap": overlap}


class KnowledgeBaseUpdate(Model):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    chunking_strategy: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("chunking_strategy")
    @classmethod
    def valid_chunking_strategy(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        if value is None:
            raise ValueError("chunking_strategy cannot be null")
        return KnowledgeBaseCreate.valid_chunking_strategy(value)

    @model_validator(mode="after")
    def at_least_one_field(self) -> KnowledgeBaseUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class KnowledgeBaseResource(Model):
    id: str
    name: str
    description: str | None = None
    chunking_strategy: dict[str, Any]
    document_count: int
    chunk_count: int
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DocumentCreate(Model):
    file_id: str
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResource(Model):
    id: str
    kb_id: str
    file_id: str
    title: str | None = None
    status: Literal["pending", "indexing", "indexed", "failed", "cancelled"]
    chunk_count: int
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    indexed_at: datetime | None = None


class SearchRequest(Model):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    threshold: float = Field(default=0, ge=0, le=1)
    filter: dict[str, Any] | None = None


class HybridSearchRequest(Model):
    query: str = Field(min_length=1)
    vector_weight: float = Field(default=0.7, ge=0)
    keyword_weight: float = Field(default=0.3, ge=0)
    top_k: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def positive_weights(self) -> HybridSearchRequest:
        if self.vector_weight + self.keyword_weight <= 0:
            raise ValueError("At least one search weight must be positive")
        return self


class ChunkResource(Model):
    id: str
    document_id: str
    document_title: str | None = None
    content: str
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResults(Model):
    query: str
    chunks: list[ChunkResource]
    total: int


class WebhookCreate(Model):
    url: HttpUrl
    events: list[str] = Field(min_length=1)
    description: str | None = None

    @field_validator("events")
    @classmethod
    def supported_events(cls, value: list[str]) -> list[str]:
        supported = {
            "file.uploaded",
            "file.deleted",
            "extraction.completed",
            "extraction.failed",
            "document.indexed",
            "document.index_failed",
        }
        unknown = sorted(set(value) - supported)
        if unknown:
            raise ValueError(f"Unsupported webhook events: {', '.join(unknown)}")
        return list(dict.fromkeys(value))


class WebhookUpdate(Model):
    url: HttpUrl | None = None
    events: list[str] | None = None
    enabled: bool | None = None
    description: str | None = None

    @field_validator("events")
    @classmethod
    def supported_events(cls, value: list[str] | None) -> list[str]:
        if value is None:
            raise ValueError("events cannot be null")
        return WebhookCreate.supported_events(value)


class WebhookResource(Model):
    id: str
    url: str
    events: list[str]
    enabled: bool
    description: str | None = None
    last_delivery_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class APIKeyCreate(Model):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def valid_scopes(cls, value: list[str]) -> list[str]:
        pattern = re.compile(r"^(files|extractions|kb|webhooks|api_keys|usage):(read|write|\*)$")
        invalid = [scope for scope in value if scope != "*" and not pattern.fullmatch(scope)]
        if invalid:
            raise ValueError(f"Invalid scopes: {', '.join(invalid)}")
        return list(dict.fromkeys(value))


class APIKeyResource(Model):
    id: str
    name: str
    key: str | None = None
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class DeletionResult(Model):
    id: str
    deleted: bool = True


T = TypeVar("T")


class ListData(Model, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


class SuccessEnvelope(Model, Generic[T]):
    success: Literal[True] = True
    data: T


class ErrorDetail(Model):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(Model):
    success: Literal[False] = False
    error: ErrorDetail


class SupportedFileTypes(Model):
    document_types: list[str]
    image_types: list[str]
    all_types: list[str]
