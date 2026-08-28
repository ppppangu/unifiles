"""Shared response and generated-model mapping helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def success(data: Any) -> dict[str, Any]:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    return {"success": True, "data": data}


def model_payload(model: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]:
    return model.model_dump(
        mode="json",
        exclude={"additional_properties"},
        exclude_unset=exclude_unset,
    )
