# coding: utf-8

from typing import Dict, List  # noqa: F401

from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi
from unifiles_server.implementation import resolve_api

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    Security,
    UploadFile,
    status,
)
from unifiles_server_protocol.models.extra_models import TokenModel  # noqa: F401
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

router = APIRouter()

@router.get(
    "/v1/webhooks",
    status_code=200,
    responses={
        200: {"model": WebhookListResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Webhooks"],
    operation_id="listWebhooks",
    summary="List Webhooks",
    response_model_by_alias=True,
)
async def list_webhooks(
    limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
    offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> WebhookListResponse:
    return await resolve_api(BaseWebhooksApi).list_webhooks(limit, offset)

@router.post(
    "/v1/webhooks",
    status_code=201,
    responses={
        201: {"model": WebhookResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Webhooks"],
    operation_id="createWebhook",
    summary="Create Webhook",
    response_model_by_alias=True,
)
async def create_webhook(
    webhook_create: WebhookCreate = Body(None, description=""),
    idempotency_key: Optional[StrictStr] = Header(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> WebhookResponse:
    return await resolve_api(BaseWebhooksApi).create_webhook(webhook_create, idempotency_key)

@router.get(
    "/v1/webhooks/{webhook_id}",
    status_code=200,
    responses={
        200: {"model": WebhookResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Webhooks"],
    operation_id="getWebhook",
    summary="Get Webhook",
    response_model_by_alias=True,
)
async def get_webhook(
    webhook_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> WebhookResponse:
    return await resolve_api(BaseWebhooksApi).get_webhook(webhook_id)

@router.delete(
    "/v1/webhooks/{webhook_id}",
    status_code=200,
    responses={
        200: {"model": DeletionResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Webhooks"],
    operation_id="deleteWebhook",
    summary="Delete Webhook",
    response_model_by_alias=True,
)
async def delete_webhook(
    webhook_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DeletionResponse:
    return await resolve_api(BaseWebhooksApi).delete_webhook(webhook_id)

@router.patch(
    "/v1/webhooks/{webhook_id}",
    status_code=200,
    responses={
        200: {"model": WebhookResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Webhooks"],
    operation_id="updateWebhook",
    summary="Update Webhook",
    response_model_by_alias=True,
)
async def update_webhook(
    webhook_id: StrictStr = Path(..., description=""),
    webhook_update: WebhookUpdate = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> WebhookResponse:
    return await resolve_api(BaseWebhooksApi).update_webhook(webhook_id, webhook_update)
