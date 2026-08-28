"""OpenAPI transport adapter for webhooks."""

from __future__ import annotations

from typing import Any

from pydantic import HttpUrl, TypeAdapter, ValidationError
from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi
from unifiles_server_protocol.models.webhook_create import WebhookCreate
from unifiles_server_protocol.models.webhook_update import WebhookUpdate

from ...shared.auth import current_context
from ...shared.errors import APIError
from ...shared.responses import model_payload, success


class WebhooksImplementation(BaseWebhooksApi):
    async def create_webhook(
        self, webhook_create: WebhookCreate, idempotency_key: str | None
    ) -> Any:
        _, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "webhooks.create")
        if cached:
            return success(cached)
        try:
            url = str(TypeAdapter(HttpUrl).validate_python(webhook_create.url))
        except ValidationError as error:
            raise APIError(422, "VALIDATION_ERROR", "url must be a valid HTTP URL") from error
        payload = model_payload(webhook_create)
        payload["url"] = url
        resource = database.create_webhook(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "webhooks.create", resource)
        return success(resource)

    async def list_webhooks(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_webhooks(principal["user_id"], limit or 50, offset or 0))

    async def get_webhook(self, webhook_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.webhook(principal["user_id"], webhook_id))

    async def update_webhook(self, webhook_id: str, webhook_update: WebhookUpdate) -> Any:
        _, principal, database = current_context()
        changes = model_payload(webhook_update, exclude_unset=True)
        if "url" in changes and webhook_update.url is not None:
            try:
                changes["url"] = str(TypeAdapter(HttpUrl).validate_python(webhook_update.url))
            except ValidationError as error:
                raise APIError(422, "VALIDATION_ERROR", "url must be a valid HTTP URL") from error
        if "events" in changes and webhook_update.events is None:
            raise APIError(422, "VALIDATION_ERROR", "events cannot be null")
        return success(database.update_webhook(principal["user_id"], webhook_id, changes))

    async def delete_webhook(self, webhook_id: str) -> Any:
        _, principal, database = current_context()
        database.delete_webhook(principal["user_id"], webhook_id)
        return success({"id": webhook_id, "deleted": True})
