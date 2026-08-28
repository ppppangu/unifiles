# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.webhook_create import WebhookCreate
from unifiles_server_protocol.models.webhook_list_response import WebhookListResponse
from unifiles_server_protocol.models.webhook_response import WebhookResponse
from unifiles_server_protocol.models.webhook_update import WebhookUpdate
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseWebhooksApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseWebhooksApi.subclasses = BaseWebhooksApi.subclasses + (cls,)
    async def list_webhooks(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> WebhookListResponse:
        ...


    async def create_webhook(
        self,
        webhook_create: WebhookCreate,
        idempotency_key: Optional[StrictStr],
    ) -> WebhookResponse:
        ...


    async def get_webhook(
        self,
        webhook_id: StrictStr,
    ) -> WebhookResponse:
        ...


    async def delete_webhook(
        self,
        webhook_id: StrictStr,
    ) -> DeletionResponse:
        ...


    async def update_webhook(
        self,
        webhook_id: StrictStr,
        webhook_update: WebhookUpdate,
    ) -> WebhookResponse:
        ...
