"""Temporary static provider exports used by generated routers during migration."""

from __future__ import annotations

from ..modules.files.dependencies import (
    get_files_api_implementation as get_files_api_implementation,
)
from ..modules.system.dependencies import (
    get_system_api_implementation as get_system_api_implementation,
)
from .handlers import (
    APIKeysImplementation,
    DocumentsImplementation,
    ExtractionsImplementation,
    KnowledgeBasesImplementation,
    SearchImplementation,
    UsageImplementation,
    WebhooksImplementation,
)

__all__ = [
    "get_api_keys_api_implementation",
    "get_documents_api_implementation",
    "get_extractions_api_implementation",
    "get_files_api_implementation",
    "get_knowledge_bases_api_implementation",
    "get_search_api_implementation",
    "get_system_api_implementation",
    "get_usage_api_implementation",
    "get_webhooks_api_implementation",
]


def get_api_keys_api_implementation() -> APIKeysImplementation:
    return APIKeysImplementation()


def get_documents_api_implementation() -> DocumentsImplementation:
    return DocumentsImplementation()


def get_extractions_api_implementation() -> ExtractionsImplementation:
    return ExtractionsImplementation()


def get_knowledge_bases_api_implementation() -> KnowledgeBasesImplementation:
    return KnowledgeBasesImplementation()


def get_search_api_implementation() -> SearchImplementation:
    return SearchImplementation()


def get_usage_api_implementation() -> UsageImplementation:
    return UsageImplementation()


def get_webhooks_api_implementation() -> WebhooksImplementation:
    return WebhooksImplementation()
