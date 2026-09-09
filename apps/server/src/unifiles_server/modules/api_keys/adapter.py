"""OpenAPI transport adapter for API-key management."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi
from unifiles_server_protocol.models.api_key_create import APIKeyCreate

from ...shared.auth import current_context
from ...shared.responses import model_payload, success


class APIKeysAdapter(BaseAPIKeysApi):
    async def create_api_key(
        self, api_key_create: APIKeyCreate, idempotency_key: str | None
    ) -> Any:
        _, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "api-keys.create")
        if cached:
            cached = database.restore_idempotent_api_key(cached)
            return success(cached)
        payload = model_payload(api_key_create)
        payload["scopes"] = payload.get("scopes") or ["*"]
        resource = database.create_api_key(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "api-keys.create", resource)
        return success(resource)

    async def list_api_keys(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_api_keys(principal["user_id"], limit or 50, offset or 0))

    async def revoke_api_key(self, key_id: str) -> Any:
        _, principal, database = current_context()
        database.revoke_api_key(principal["user_id"], key_id)
        return success({"id": key_id, "deleted": True})
