from __future__ import annotations

import ast
from pathlib import Path

from unifiles_server import auth, errors, services, settings, store
from unifiles_server.implementation import handlers, providers
from unifiles_server.modules.api_keys import dependencies as api_key_dependencies
from unifiles_server.modules.api_keys import implementation as api_key_implementation
from unifiles_server.modules.documents import dependencies as document_dependencies
from unifiles_server.modules.documents import implementation as document_implementation
from unifiles_server.modules.documents import service as document_service
from unifiles_server.modules.extractions import dependencies as extraction_dependencies
from unifiles_server.modules.extractions import implementation as extraction_implementation
from unifiles_server.modules.extractions import service as extraction_service
from unifiles_server.modules.files import dependencies as file_dependencies
from unifiles_server.modules.files import implementation as file_implementation
from unifiles_server.modules.knowledge_bases import dependencies as kb_dependencies
from unifiles_server.modules.knowledge_bases import implementation as kb_implementation
from unifiles_server.modules.search import dependencies as search_dependencies
from unifiles_server.modules.search import implementation as search_implementation
from unifiles_server.modules.search import service as search_service
from unifiles_server.modules.system import dependencies as system_dependencies
from unifiles_server.modules.system import implementation as system_implementation
from unifiles_server.modules.usage import dependencies as usage_dependencies
from unifiles_server.modules.usage import implementation as usage_implementation
from unifiles_server.modules.webhooks import dependencies as webhook_dependencies
from unifiles_server.modules.webhooks import implementation as webhook_implementation
from unifiles_server.modules.webhooks import service as webhook_service
from unifiles_server.shared import auth as shared_auth
from unifiles_server.shared import database as shared_database
from unifiles_server.shared import errors as shared_errors
from unifiles_server.shared import settings as shared_settings


def test_central_provider_module_is_only_static_compatibility() -> None:
    expected = {
        "get_api_keys_api_implementation": api_key_dependencies.get_api_keys_api_implementation,
        "get_documents_api_implementation": document_dependencies.get_documents_api_implementation,
        "get_extractions_api_implementation": (
            extraction_dependencies.get_extractions_api_implementation
        ),
        "get_files_api_implementation": file_dependencies.get_files_api_implementation,
        "get_knowledge_bases_api_implementation": (
            kb_dependencies.get_knowledge_bases_api_implementation
        ),
        "get_search_api_implementation": search_dependencies.get_search_api_implementation,
        "get_system_api_implementation": system_dependencies.get_system_api_implementation,
        "get_usage_api_implementation": usage_dependencies.get_usage_api_implementation,
        "get_webhooks_api_implementation": webhook_dependencies.get_webhooks_api_implementation,
    }
    for name, provider in expected.items():
        assert getattr(providers, name) is provider


def test_central_handler_module_is_only_static_compatibility() -> None:
    expected = {
        "APIKeysImplementation": api_key_implementation.APIKeysImplementation,
        "DocumentsImplementation": document_implementation.DocumentsImplementation,
        "ExtractionsImplementation": extraction_implementation.ExtractionsImplementation,
        "FilesImplementation": file_implementation.FilesImplementation,
        "KnowledgeBasesImplementation": kb_implementation.KnowledgeBasesImplementation,
        "SearchImplementation": search_implementation.SearchImplementation,
        "SystemImplementation": system_implementation.SystemImplementation,
        "UsageImplementation": usage_implementation.UsageImplementation,
        "WebhooksImplementation": webhook_implementation.WebhooksImplementation,
    }
    for name, implementation in expected.items():
        assert getattr(handlers, name) is implementation


def test_top_level_infrastructure_modules_are_static_compatibility() -> None:
    assert auth.authenticate_request is shared_auth.authenticate_request
    assert errors.APIError is shared_errors.APIError
    assert settings.Settings is shared_settings.Settings
    assert store.Store is shared_database.Store


def test_top_level_services_are_static_compatibility() -> None:
    assert services.run_extraction is extraction_service.run_extraction
    assert services.run_indexing is document_service.run_indexing
    assert services.search is search_service.search
    assert services.dispatch_event is webhook_service.dispatch_event


def test_compatibility_modules_define_no_runtime_classes_or_functions() -> None:
    compatibility_modules = [auth, errors, handlers, providers, services, settings, store]
    for module in compatibility_modules:
        path = Path(module.__file__ or "")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not definitions, f"{module.__name__} contains compatibility logic"
