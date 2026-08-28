"""Shared helpers for validating and inventorying the canonical OpenAPI contract."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}

BUSINESS_TAGS: dict[str, tuple[str, str]] = {
    "API Keys": ("api_keys", "APIKeys"),
    "Documents": ("documents", "Documents"),
    "Extractions": ("extractions", "Extractions"),
    "Files": ("files", "Files"),
    "Knowledge Bases": ("knowledge_bases", "KnowledgeBases"),
    "Search": ("search", "Search"),
    "System": ("system", "System"),
    "Usage": ("usage", "Usage"),
    "Webhooks": ("webhooks", "Webhooks"),
}
PUBLIC_PATHS = {"/health", "/v1/health"}


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate keys instead of silently overwriting them."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_openapi(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    if not isinstance(value, dict):
        raise ValueError(f"OpenAPI document must be a mapping: {path}")
    return value


def iter_operations(
    document: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI document is missing a paths mapping")
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                raise ValueError(f"{method.upper()} {path} must be an operation mapping")
            yield str(path), method, operation


def validate_openapi_invariants(document: dict[str, Any]) -> list[str]:
    operation_ids: list[str] = []
    for path, method, operation in iter_operations(document):
        operation_id = operation.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError(f"{method.upper()} {path} is missing operationId")
        if not re.fullmatch(r"[a-z][A-Za-z0-9]*", operation_id):
            raise ValueError(f"operationId must be lower camelCase: {operation_id}")
        operation_ids.append(operation_id)

        tags = operation.get("tags")
        if not isinstance(tags, list) or len(tags) != 1:
            raise ValueError(f"{method.upper()} {path} must have exactly one business tag")
        if tags[0] not in BUSINESS_TAGS:
            raise ValueError(f"{method.upper()} {path} uses unknown business tag: {tags[0]}")

        expected_security: list[dict[str, list[str]]] = (
            [] if path in PUBLIC_PATHS else [{"BearerAuth": []}]
        )
        if operation.get("security") != expected_security:
            requirement = "public security: []" if not expected_security else "BearerAuth"
            raise ValueError(f"{method.upper()} {path} must require {requirement}")

    duplicates = sorted({item for item in operation_ids if operation_ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"duplicate operationId values: {', '.join(duplicates)}")
    return operation_ids
