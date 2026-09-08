"""OpenAPI transport adapter for knowledge bases."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi
from unifiles_server_protocol.models.knowledge_base_create import KnowledgeBaseCreate
from unifiles_server_protocol.models.knowledge_base_update import KnowledgeBaseUpdate

from ...shared.auth import current_context
from ...shared.errors import APIError
from ...shared.responses import model_payload, success
from .service import normalize_chunking


class KnowledgeBasesAdapter(BaseKnowledgeBasesApi):
    async def create_knowledge_base(
        self, knowledge_base_create: KnowledgeBaseCreate, idempotency_key: str | None
    ) -> Any:
        request, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "kb.create")
        if cached:
            return success(cached)
        if (
            database.usage(principal["user_id"])["knowledge_bases"]["used"]
            >= request.app.state.settings.knowledge_base_limit
        ):
            raise APIError(403, "QUOTA_EXCEEDED", "Knowledge base quota exceeded")
        payload = model_payload(knowledge_base_create)
        payload["chunking_strategy"] = normalize_chunking(knowledge_base_create.chunking_strategy)
        payload["metadata"] = payload.get("metadata") or {}
        resource = database.create_kb(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "kb.create", resource)
        return success(resource)

    async def list_knowledge_bases(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_kbs(principal["user_id"], limit or 50, offset or 0))

    async def get_knowledge_base(self, kb_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.kb(principal["user_id"], kb_id))

    async def update_knowledge_base(
        self, kb_id: str, knowledge_base_update: KnowledgeBaseUpdate
    ) -> Any:
        _, principal, database = current_context()
        fields = knowledge_base_update.model_fields_set - {"additional_properties"}
        if not fields:
            raise APIError(422, "VALIDATION_ERROR", "At least one field is required")
        changes = model_payload(knowledge_base_update, exclude_unset=True)
        if "chunking_strategy" in changes:
            if knowledge_base_update.chunking_strategy is None:
                raise APIError(422, "VALIDATION_ERROR", "chunking_strategy cannot be null")
            changes["chunking_strategy"] = normalize_chunking(
                knowledge_base_update.chunking_strategy
            )
        return success(database.update_kb(principal["user_id"], kb_id, changes))

    async def delete_knowledge_base(self, kb_id: str) -> Any:
        _, principal, database = current_context()
        database.delete_kb(principal["user_id"], kb_id)
        return success({"id": kb_id, "deleted": True})
