from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from unifiles_server.app import create_app
from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi
from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi
from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi
from unifiles_server_protocol.apis.files_api_base import BaseFilesApi
from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi
from unifiles_server_protocol.apis.search_api_base import BaseSearchApi
from unifiles_server_protocol.apis.system_api_base import BaseSystemApi
from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi
from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi

REPO_ROOT = Path(__file__).parents[3]
GENERATED_PROTOCOL = (
    REPO_ROOT / "packages" / "generated" / "server-protocol-python" / "src"
)
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def test_routes_are_unique() -> None:
    app = create_app()
    seen: set[tuple[str, str]] = set()

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, route.path)
            assert key not in seen, f"Duplicate route: {method} {route.path}"
            seen.add(key)


def test_operation_ids_are_unique() -> None:
    operation_ids: list[str] = []
    for route in create_app().routes:
        if not isinstance(route, APIRoute):
            continue
        assert route.operation_id is not None, f"Missing operationId: {route.path}"
        operation_ids.append(route.operation_id)

    assert len(operation_ids) == len(set(operation_ids))


def test_composed_app_routes_exactly_match_canonical_contract() -> None:
    app = create_app()
    actual = {
        (method, route.path, route.operation_id)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }
    expected = {
        (method.upper(), path, operation["operationId"])
        for path, path_item in app.openapi()["paths"].items()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    }

    assert actual == expected


def test_generated_protocol_does_not_import_server_application() -> None:
    violations: list[str] = []
    for path in GENERATED_PROTOCOL.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                if module == "unifiles_server" or module.startswith("unifiles_server."):
                    violations.append(f"{path}: {module}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize(
    "base_api",
    [
        BaseAPIKeysApi,
        BaseDocumentsApi,
        BaseExtractionsApi,
        BaseFilesApi,
        BaseKnowledgeBasesApi,
        BaseSearchApi,
        BaseSystemApi,
        BaseUsageApi,
        BaseWebhooksApi,
    ],
)
def test_generated_base_apis_are_abstract(base_api: type) -> None:
    assert inspect.isabstract(base_api)
    assert not hasattr(base_api, "subclasses")
    with pytest.raises(TypeError):
        base_api()


def test_app_composition_uses_no_dynamic_router_discovery() -> None:
    path = REPO_ROOT / "apps" / "server" / "src" / "unifiles_server" / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported_modules.isdisjoint({"importlib", "pkgutil"})
