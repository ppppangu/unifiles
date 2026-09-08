from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from unifiles_server.app import create_app
from unifiles_server.modules.api_keys.providers import provide_api_keys_adapter
from unifiles_server.modules.api_keys.router import router as api_keys_router
from unifiles_server.modules.documents.providers import provide_documents_adapter
from unifiles_server.modules.documents.router import router as documents_router
from unifiles_server.modules.extractions.providers import provide_extractions_adapter
from unifiles_server.modules.extractions.router import router as extractions_router
from unifiles_server.modules.files.providers import provide_files_adapter
from unifiles_server.modules.files.router import router as files_router
from unifiles_server.modules.knowledge_bases.providers import (
    provide_knowledge_bases_adapter,
)
from unifiles_server.modules.knowledge_bases.router import router as knowledge_bases_router
from unifiles_server.modules.search.providers import provide_search_adapter
from unifiles_server.modules.search.router import router as search_router
from unifiles_server.modules.system.providers import provide_system_adapter
from unifiles_server.modules.system.router import router as system_router
from unifiles_server.modules.usage.providers import provide_usage_adapter
from unifiles_server.modules.usage.router import router as usage_router
from unifiles_server.modules.webhooks.providers import provide_webhooks_adapter
from unifiles_server.modules.webhooks.router import router as webhooks_router
from unifiles_server.shared.auth import get_bearer_auth
from unifiles_server.shared.settings import Settings

MODULE_ROUTERS = [
    (api_keys_router, provide_api_keys_adapter),
    (documents_router, provide_documents_adapter),
    (extractions_router, provide_extractions_adapter),
    (files_router, provide_files_adapter),
    (knowledge_bases_router, provide_knowledge_bases_adapter),
    (search_router, provide_search_adapter),
    (system_router, provide_system_adapter),
    (usage_router, provide_usage_adapter),
    (webhooks_router, provide_webhooks_adapter),
]
PUBLIC_PATHS = {"/health", "/v1/health"}


def test_every_module_statically_binds_generated_routes() -> None:
    for router, adapter_provider in MODULE_ROUTERS:
        assert isinstance(router, APIRouter)
        assert router.routes
        for route in router.routes:
            assert isinstance(route, APIRoute)
            dependencies = [dependency.call for dependency in route.dependant.dependencies]
            assert adapter_provider in dependencies
            if route.path in PUBLIC_PATHS:
                assert get_bearer_auth not in dependencies
            else:
                assert get_bearer_auth in dependencies
                assert dependencies.index(get_bearer_auth) < dependencies.index(
                    adapter_provider
                )


def test_unauthenticated_request_does_not_construct_implementation(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, bootstrap_api_key="sk_test"))
    provider_calls: list[bool] = []

    def fail_if_called() -> None:
        provider_calls.append(True)
        raise AssertionError("adapter provider ran before authentication")

    app.dependency_overrides[provide_files_adapter] = fail_if_called
    with TestClient(app) as client:
        response = client.get("/v1/files/types")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_API_KEY"
    assert provider_calls == []


def test_compatibility_packages_have_been_removed() -> None:
    for module_name in (
        "unifiles_server.auth",
        "unifiles_server.errors",
        "unifiles_server.implementation",
        "unifiles_server.services",
        "unifiles_server.settings",
        "unifiles_server.store",
    ):
        assert importlib.util.find_spec(module_name) is None
