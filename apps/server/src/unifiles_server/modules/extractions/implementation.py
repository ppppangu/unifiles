"""OpenAPI transport adapter for content extractions."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi
from unifiles_server_protocol.models.extraction_create import ExtractionCreate

from ...shared.auth import current_context
from ...shared.responses import success
from .service import run_extraction


class ExtractionsImplementation(BaseExtractionsApi):
    async def list_file_extractions(
        self, file_id: str, limit: int | None, offset: int | None
    ) -> Any:
        _, principal, database = current_context()
        return success(
            database.list_extractions(principal["user_id"], file_id, limit or 50, offset or 0)
        )

    async def create_extraction(
        self, extraction_create: ExtractionCreate, idempotency_key: str | None
    ) -> Any:
        request, principal, database = current_context()
        cached = database.idempotent_get(
            principal["user_id"], idempotency_key, "extractions.create"
        )
        if cached:
            return success(cached)
        options = (
            extraction_create.options.model_dump(mode="json", exclude_none=True)
            if extraction_create.options is not None
            else {}
        )
        resource = database.create_extraction(
            principal["user_id"],
            extraction_create.file_id,
            extraction_create.mode or "normal",
            options,
        )
        database.idempotent_put(
            principal["user_id"], idempotency_key, "extractions.create", resource
        )
        request.app.state.executor.submit(
            run_extraction, database, principal["user_id"], resource["id"]
        )
        return success(resource)

    async def get_extraction(self, extraction_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.extraction(principal["user_id"], extraction_id))
