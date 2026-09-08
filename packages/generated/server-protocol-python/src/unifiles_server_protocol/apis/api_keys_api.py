# coding: utf-8

from collections.abc import Callable
from typing import Annotated, Dict, List, TypeAlias  # noqa: F401

from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi

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
from unifiles_server_protocol.models.api_key_create import APIKeyCreate
from unifiles_server_protocol.models.api_key_list_response import APIKeyListResponse
from unifiles_server_protocol.models.api_key_response import APIKeyResponse
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.security_api import SecurityProvider

AdapterProvider: TypeAlias = Callable[..., BaseAPIKeysApi]


def create_router(
    get_adapter: AdapterProvider,
    get_token_BearerAuth: SecurityProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/v1/api-keys",
        status_code=200,
        responses={
            200: {"model": APIKeyListResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["API Keys"],
        operation_id="listApiKeys",
        summary="List Api Keys",
        response_model_by_alias=True,
    )
    async def list_api_keys(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseAPIKeysApi,
            Depends(get_adapter),
        ],
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
    ) -> APIKeyListResponse:
        return await adapter.list_api_keys(limit, offset)

    @router.post(
        "/v1/api-keys",
        status_code=201,
        responses={
            201: {"model": APIKeyResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["API Keys"],
        operation_id="createApiKey",
        summary="Create Api Key",
        response_model_by_alias=True,
    )
    async def create_api_key(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseAPIKeysApi,
            Depends(get_adapter),
        ],
        api_key_create: APIKeyCreate = Body(None, description=""),
        idempotency_key: Optional[StrictStr] = Header(None, description=""),
    ) -> APIKeyResponse:
        return await adapter.create_api_key(api_key_create, idempotency_key)

    @router.delete(
        "/v1/api-keys/{key_id}",
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
        tags=["API Keys"],
        operation_id="revokeApiKey",
        summary="Revoke Api Key",
        response_model_by_alias=True,
    )
    async def revoke_api_key(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseAPIKeysApi,
            Depends(get_adapter),
        ],
        key_id: StrictStr = Path(..., description=""),
    ) -> DeletionResponse:
        return await adapter.revoke_api_key(key_id)
    return router
