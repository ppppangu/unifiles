"""FastAPI dependency providers for handwritten API implementations."""

from __future__ import annotations

from .handlers import (
    APIKeysImplementation,
    DocumentsImplementation,
    ExtractionsImplementation,
    FilesImplementation,
    KnowledgeBasesImplementation,
    SearchImplementation,
    SystemImplementation,
    UsageImplementation,
    WebhooksImplementation,
)


def get_api_keys_api_implementation() -> APIKeysImplementation:
    return APIKeysImplementation()


def get_documents_api_implementation() -> DocumentsImplementation:
    return DocumentsImplementation()


def get_extractions_api_implementation() -> ExtractionsImplementation:
    return ExtractionsImplementation()


def get_files_api_implementation() -> FilesImplementation:
    return FilesImplementation()


def get_knowledge_bases_api_implementation() -> KnowledgeBasesImplementation:
    return KnowledgeBasesImplementation()


def get_search_api_implementation() -> SearchImplementation:
    return SearchImplementation()


def get_system_api_implementation() -> SystemImplementation:
    return SystemImplementation()


def get_usage_api_implementation() -> UsageImplementation:
    return UsageImplementation()


def get_webhooks_api_implementation() -> WebhooksImplementation:
    return WebhooksImplementation()
