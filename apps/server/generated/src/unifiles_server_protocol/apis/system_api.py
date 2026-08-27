# coding: utf-8

from typing import Dict, List  # noqa: F401

from unifiles_server_protocol.apis.system_api_base import BaseSystemApi
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
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.health_response import HealthResponse


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
) -> HealthResponse:
    return await resolve_api(BaseSystemApi).get_versioned_health()

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
) -> HealthResponse:
    return await resolve_api(BaseSystemApi).get_health()
