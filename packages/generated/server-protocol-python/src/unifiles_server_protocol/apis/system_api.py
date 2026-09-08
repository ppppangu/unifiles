# coding: utf-8

from collections.abc import Callable
from typing import Annotated, Dict, List, TypeAlias  # noqa: F401

from unifiles_server_protocol.apis.system_api_base import BaseSystemApi

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
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.health_details_response import HealthDetailsResponse
from unifiles_server_protocol.models.health_response import HealthResponse
from unifiles_server_protocol.security_api import SecurityProvider

AdapterProvider: TypeAlias = Callable[..., BaseSystemApi]


def create_router(
    get_adapter: AdapterProvider,
    get_token_BearerAuth: SecurityProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/v1/health",
        status_code=200,
        responses={
            200: {"model": HealthResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["System"],
        operation_id="getVersionedHealth",
        summary="Health",
        response_model_by_alias=True,
    )
    async def get_versioned_health(
        adapter: Annotated[
            BaseSystemApi,
            Depends(get_adapter),
        ],
    ) -> HealthResponse:
        return await adapter.get_versioned_health()

    @router.get(
        "/v1/health/details",
        status_code=200,
        responses={
            200: {"model": HealthDetailsResponse, "description": "Detailed service health"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission denied"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["System"],
        operation_id="getHealthDetails",
        summary="Detailed Health",
        response_model_by_alias=True,
    )
    async def get_health_details(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseSystemApi,
            Depends(get_adapter),
        ],
    ) -> HealthDetailsResponse:
        return await adapter.get_health_details()

    @router.get(
        "/health",
        status_code=200,
        responses={
            200: {"model": HealthResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["System"],
        operation_id="getHealth",
        summary="Health",
        response_model_by_alias=True,
    )
    async def get_health(
        adapter: Annotated[
            BaseSystemApi,
            Depends(get_adapter),
        ],
    ) -> HealthResponse:
        return await adapter.get_health()
    return router
