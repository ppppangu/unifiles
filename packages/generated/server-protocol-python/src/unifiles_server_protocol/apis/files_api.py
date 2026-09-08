# coding: utf-8

from collections.abc import Callable
from typing import Annotated, Dict, List, TypeAlias  # noqa: F401

from unifiles_server_protocol.apis.files_api_base import BaseFilesApi

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
from pydantic import Field, StrictBytes, StrictStr
from typing import Optional, Tuple, Union
from typing_extensions import Annotated
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.file_list_response import FileListResponse
from unifiles_server_protocol.models.file_response import FileResponse
from unifiles_server_protocol.models.supported_file_types_response import SupportedFileTypesResponse
from fastapi import File, UploadFile
from unifiles_server_protocol.security_api import SecurityProvider

AdapterProvider: TypeAlias = Callable[..., BaseFilesApi]


def create_router(
    get_adapter: AdapterProvider,
    get_token_BearerAuth: SecurityProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/v1/files/types",
        status_code=200,
        responses={
            200: {"model": SupportedFileTypesResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Files"],
        operation_id="listSupportedFileTypes",
        summary="Supported Types",
        response_model_by_alias=True,
    )
    async def list_supported_file_types(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
    ) -> SupportedFileTypesResponse:
        return await adapter.list_supported_file_types()

    @router.get(
        "/v1/files",
        status_code=200,
        responses={
            200: {"model": FileListResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Files"],
        operation_id="listFiles",
        summary="List Files",
        response_model_by_alias=True,
    )
    async def list_files(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
        tags: Optional[StrictStr] = Query(None, description="", alias="tags"),
        content_type: Optional[StrictStr] = Query(None, description="", alias="content_type"),
        sort_by: Optional[StrictStr] = Query('created_at', description="", alias="sort_by"),
        order: Optional[StrictStr] = Query('desc', description="", alias="order"),
    ) -> FileListResponse:
        return await adapter.list_files(limit, offset, tags, content_type, sort_by, order)

    @router.post(
        "/v1/files",
        status_code=201,
        responses={
            201: {"model": FileResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
            413: {"model": ErrorEnvelope, "description": "File too large"},
        },
        tags=["Files"],
        operation_id="uploadFile",
        summary="Upload File",
        response_model_by_alias=True,
    )
    async def upload_file(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
        file: UploadFile = File(..., description=""),
        idempotency_key: Optional[StrictStr] = Header(None, description=""),
        metadata: Optional[StrictStr] = Form('{}', description=""),
        tags: Optional[StrictStr] = Form('[]', description=""),
    ) -> FileResponse:
        return await adapter.upload_file(file, idempotency_key, metadata, tags)

    @router.get(
        "/v1/files/{file_id}",
        status_code=200,
        responses={
            200: {"model": FileResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Files"],
        operation_id="getFile",
        summary="Get File",
        response_model_by_alias=True,
    )
    async def get_file(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
        file_id: StrictStr = Path(..., description=""),
    ) -> FileResponse:
        return await adapter.get_file(file_id)

    @router.delete(
        "/v1/files/{file_id}",
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
        tags=["Files"],
        operation_id="deleteFile",
        summary="Delete File",
        response_model_by_alias=True,
    )
    async def delete_file(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
        file_id: StrictStr = Path(..., description=""),
    ) -> DeletionResponse:
        return await adapter.delete_file(file_id)

    @router.get(
        "/v1/files/{file_id}/download",
        status_code=200,
        responses={
            200: {"model": bytes, "description": "File content"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Files"],
        operation_id="downloadFile",
        summary="Download File",
        response_model_by_alias=True,
    )
    async def download_file(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseFilesApi,
            Depends(get_adapter),
        ],
        file_id: StrictStr = Path(..., description=""),
    ) -> bytes:
        return await adapter.download_file(file_id)
    return router
