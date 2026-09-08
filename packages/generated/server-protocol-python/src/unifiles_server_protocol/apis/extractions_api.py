# coding: utf-8

from collections.abc import Callable
from typing import Annotated, Dict, List, TypeAlias  # noqa: F401

from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi

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
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.extraction_create import ExtractionCreate
from unifiles_server_protocol.models.extraction_list_response import ExtractionListResponse
from unifiles_server_protocol.models.extraction_response import ExtractionResponse
from unifiles_server_protocol.security_api import SecurityProvider

AdapterProvider: TypeAlias = Callable[..., BaseExtractionsApi]


def create_router(
    get_adapter: AdapterProvider,
    get_token_BearerAuth: SecurityProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/v1/files/{file_id}/extractions",
        status_code=200,
        responses={
            200: {"model": ExtractionListResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Extractions"],
        operation_id="listFileExtractions",
        summary="File Extractions",
        response_model_by_alias=True,
    )
    async def list_file_extractions(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseExtractionsApi,
            Depends(get_adapter),
        ],
        file_id: StrictStr = Path(..., description=""),
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
    ) -> ExtractionListResponse:
        return await adapter.list_file_extractions(file_id, limit, offset)

    @router.post(
        "/v1/extractions",
        status_code=202,
        responses={
            202: {"model": ExtractionResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Extractions"],
        operation_id="createExtraction",
        summary="Create Extraction",
        response_model_by_alias=True,
    )
    async def create_extraction(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseExtractionsApi,
            Depends(get_adapter),
        ],
        extraction_create: ExtractionCreate = Body(None, description=""),
        idempotency_key: Optional[StrictStr] = Header(None, description=""),
    ) -> ExtractionResponse:
        return await adapter.create_extraction(extraction_create, idempotency_key)

    @router.get(
        "/v1/extractions/{extraction_id}",
        status_code=200,
        responses={
            200: {"model": ExtractionResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Extractions"],
        operation_id="getExtraction",
        summary="Get Extraction",
        response_model_by_alias=True,
    )
    async def get_extraction(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseExtractionsApi,
            Depends(get_adapter),
        ],
        extraction_id: StrictStr = Path(..., description=""),
    ) -> ExtractionResponse:
        return await adapter.get_extraction(extraction_id)
    return router
