"""Knowledge-base configuration rules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ...shared.errors import APIError


def normalize_chunking(value: Any | None) -> dict[str, Any]:
    result: dict[str, Any]
    if value is None:
        result = {"type": "semantic", "chunk_size": 512, "overlap": 50}
    elif isinstance(value, BaseModel):
        result = value.model_dump(mode="json", exclude={"additional_properties"})
    else:
        result = dict(value)
    chunk_size = int(result.get("chunk_size", 512))
    overlap = int(result.get("overlap", 50))
    if overlap >= chunk_size:
        raise APIError(422, "VALIDATION_ERROR", "overlap must be smaller than chunk_size")
    return {**result, "chunk_size": chunk_size, "overlap": overlap}
