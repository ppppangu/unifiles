# coding: utf-8

from typing import Annotated, Dict, List  # noqa: F401

from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi
from unifiles_server.implementation.providers import get_usage_api_implementation

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
from unifiles_server_protocol.models.usage_limits_response import UsageLimitsResponse
from unifiles_server_protocol.models.usage_stats_response import UsageStatsResponse
from unifiles_server_protocol.security_api import get_token_BearerAuth

router = APIRouter()

@router.get(
    "/v1/usage/stats",
    status_code=200,
    responses={
        200: {"model": UsageStatsResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Usage"],
    operation_id="getUsageStats",
    summary="Usage Stats",
    response_model_by_alias=True,
)
async def get_usage_stats(
    implementation: Annotated[
        BaseUsageApi,
        Depends(get_usage_api_implementation),
    ],
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> UsageStatsResponse:
    return await implementation.get_usage_stats()

@router.get(
    "/v1/usage/limits",
    status_code=200,
    responses={
        200: {"model": UsageLimitsResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Usage"],
    operation_id="getUsageLimits",
    summary="Usage Limits",
    response_model_by_alias=True,
)
async def get_usage_limits(
    implementation: Annotated[
        BaseUsageApi,
        Depends(get_usage_api_implementation),
    ],
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> UsageLimitsResponse:
    return await implementation.get_usage_limits()
