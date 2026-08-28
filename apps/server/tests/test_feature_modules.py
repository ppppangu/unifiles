from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from unifiles_server.app import create_app
from unifiles_server.modules.api_keys.api import router as api_keys_router
from unifiles_server.modules.api_keys.dependencies import get_api_keys_api_implementation
from unifiles_server.modules.documents.api import router as documents_router
from unifiles_server.modules.documents.dependencies import get_documents_api_implementation
from unifiles_server.modules.extractions.api import router as extractions_router
from unifiles_server.modules.extractions.dependencies import get_extractions_api_implementation
from unifiles_server.modules.files.api import router as files_router
from unifiles_server.modules.files.dependencies import get_files_api_implementation
from unifiles_server.modules.knowledge_bases.api import router as knowledge_bases_router
from unifiles_server.modules.knowledge_bases.dependencies import (
    get_knowledge_bases_api_implementation,
)
from unifiles_server.modules.search.api import router as search_router
from unifiles_server.modules.search.dependencies import get_search_api_implementation
from unifiles_server.modules.system.api import router as system_router
from unifiles_server.modules.system.dependencies import get_system_api_implementation
from unifiles_server.modules.usage.api import router as usage_router
from unifiles_server.modules.usage.dependencies import get_usage_api_implementation
from unifiles_server.modules.webhooks.api import router as webhooks_router
from unifiles_server.modules.webhooks.dependencies import get_webhooks_api_implementation
from unifiles_server.shared.auth import get_bearer_auth
from unifiles_server.shared.settings import Settings

MODULE_ROUTERS = [
    (api_keys_router, get_api_keys_api_implementation),
    (documents_router, get_documents_api_implementation),
    (extractions_router, get_extractions_api_implementation),
    (files_router, get_files_api_implementation),
    (knowledge_bases_router, get_knowledge_bases_api_implementation),
    (search_router, get_search_api_implementation),
    (system_router, get_system_api_implementation),
    (usage_router, get_usage_api_implementation),
    (webhooks_router, get_webhooks_api_implementation),
]
PUBLIC_PATHS = {"/health", "/v1/health"}


def test_every_module_statically_binds_generated_routes() -> None:
    for router, implementation_provider in MODULE_ROUTERS:
        assert isinstance(router, APIRouter)
        assert router.routes
        for route in router.routes:
            assert isinstance(route, APIRoute)
            dependencies = [dependency.call for dependency in route.dependant.dependencies]
            assert implementation_provider in dependencies
            if route.path in PUBLIC_PATHS:
                assert get_bearer_auth not in dependencies
            else:
                assert get_bearer_auth in dependencies
                assert dependencies.index(get_bearer_auth) < dependencies.index(
                    implementation_provider
                )


def test_unauthenticated_request_does_not_construct_implementation(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, bootstrap_api_key="sk_test"))
    provider_calls: list[bool] = []

    def fail_if_called() -> None:
        provider_calls.append(True)
        raise AssertionError("implementation provider ran before authentication")

    app.dependency_overrides[get_files_api_implementation] = fail_if_called
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
