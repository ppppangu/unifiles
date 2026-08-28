from __future__ import annotations

from fastapi.routing import APIRoute
from unifiles_server.app import create_app


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
