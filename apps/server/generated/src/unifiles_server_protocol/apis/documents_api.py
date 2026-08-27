# coding: utf-8

from typing import Dict, List  # noqa: F401

from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi
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
from unifiles_server_protocol.models.document_create import DocumentCreate
from unifiles_server_protocol.models.document_list_response import DocumentListResponse
from unifiles_server_protocol.models.document_response import DocumentResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.security_api import get_token_BearerAuth

router = APIRouter()

@router.get(
    "/v1/knowledge-bases/{kb_id}/documents",
    status_code=200,
    responses={
        200: {"model": DocumentListResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Documents"],
    operation_id="listDocuments",
    summary="List Documents",
    response_model_by_alias=True,
)
async def list_documents(
    kb_id: StrictStr = Path(..., description=""),
    limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
    offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DocumentListResponse:
    return await resolve_api(BaseDocumentsApi).list_documents(kb_id, limit, offset)

@router.post(
    "/v1/knowledge-bases/{kb_id}/documents",
    status_code=202,
    responses={
        202: {"model": DocumentResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Documents"],
    operation_id="createDocument",
    summary="Create Document",
    response_model_by_alias=True,
)
async def create_document(
    kb_id: StrictStr = Path(..., description=""),
    document_create: DocumentCreate = Body(None, description=""),
    idempotency_key: Optional[StrictStr] = Header(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DocumentResponse:
    return await resolve_api(BaseDocumentsApi).create_document(kb_id, document_create, idempotency_key)

@router.get(
    "/v1/knowledge-bases/{kb_id}/documents/{document_id}",
    status_code=200,
    responses={
        200: {"model": DocumentResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Documents"],
    operation_id="getDocument",
    summary="Get Document",
    response_model_by_alias=True,
)
async def get_document(
    kb_id: StrictStr = Path(..., description=""),
    document_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DocumentResponse:
    return await resolve_api(BaseDocumentsApi).get_document(kb_id, document_id)

@router.delete(
    "/v1/knowledge-bases/{kb_id}/documents/{document_id}",
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
    tags=["Documents"],
    operation_id="deleteDocument",
    summary="Delete Document",
    response_model_by_alias=True,
)
async def delete_document(
    kb_id: StrictStr = Path(..., description=""),
    document_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DeletionResponse:
    return await resolve_api(BaseDocumentsApi).delete_document(kb_id, document_id)
