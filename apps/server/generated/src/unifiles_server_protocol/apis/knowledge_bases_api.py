# coding: utf-8

from typing import Annotated, Dict, List  # noqa: F401

from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi
from unifiles_server.implementation.providers import get_knowledge_bases_api_implementation

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
from unifiles_server_protocol.models.knowledge_base_create import KnowledgeBaseCreate
from unifiles_server_protocol.models.knowledge_base_list_response import KnowledgeBaseListResponse
from unifiles_server_protocol.models.knowledge_base_response import KnowledgeBaseResponse
from unifiles_server_protocol.models.knowledge_base_update import KnowledgeBaseUpdate
from unifiles_server_protocol.security_api import get_token_BearerAuth

router = APIRouter()

@router.get(
    "/v1/knowledge-bases",
    status_code=200,
    responses={
        200: {"model": KnowledgeBaseListResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Knowledge Bases"],
    operation_id="listKnowledgeBases",
    summary="List Knowledge Bases",
    response_model_by_alias=True,
)
async def list_knowledge_bases(
    implementation: Annotated[
        BaseKnowledgeBasesApi,
        Depends(get_knowledge_bases_api_implementation),
    ],
    limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]] = Query(50, description="", alias="limit", ge=1, le=100),
    offset: Optional[Annotated[int, Field(strict=True, ge=0)]] = Query(0, description="", alias="offset", ge=0),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> KnowledgeBaseListResponse:
    return await implementation.list_knowledge_bases(limit, offset)

@router.post(
    "/v1/knowledge-bases",
    status_code=201,
    responses={
        201: {"model": KnowledgeBaseResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Knowledge Bases"],
    operation_id="createKnowledgeBase",
    summary="Create Knowledge Base",
    response_model_by_alias=True,
)
async def create_knowledge_base(
    implementation: Annotated[
        BaseKnowledgeBasesApi,
        Depends(get_knowledge_bases_api_implementation),
    ],
    knowledge_base_create: KnowledgeBaseCreate = Body(None, description=""),
    idempotency_key: Optional[StrictStr] = Header(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> KnowledgeBaseResponse:
    return await implementation.create_knowledge_base(knowledge_base_create, idempotency_key)

@router.get(
    "/v1/knowledge-bases/{kb_id}",
    status_code=200,
    responses={
        200: {"model": KnowledgeBaseResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Knowledge Bases"],
    operation_id="getKnowledgeBase",
    summary="Get Knowledge Base",
    response_model_by_alias=True,
)
async def get_knowledge_base(
    implementation: Annotated[
        BaseKnowledgeBasesApi,
        Depends(get_knowledge_bases_api_implementation),
    ],
    kb_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> KnowledgeBaseResponse:
    return await implementation.get_knowledge_base(kb_id)

@router.delete(
    "/v1/knowledge-bases/{kb_id}",
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
    tags=["Knowledge Bases"],
    operation_id="deleteKnowledgeBase",
    summary="Delete Knowledge Base",
    response_model_by_alias=True,
)
async def delete_knowledge_base(
    implementation: Annotated[
        BaseKnowledgeBasesApi,
        Depends(get_knowledge_bases_api_implementation),
    ],
    kb_id: StrictStr = Path(..., description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> DeletionResponse:
    return await implementation.delete_knowledge_base(kb_id)

@router.patch(
    "/v1/knowledge-bases/{kb_id}",
    status_code=200,
    responses={
        200: {"model": KnowledgeBaseResponse, "description": "Successful Response"},
        400: {"model": ErrorEnvelope, "description": "Invalid request"},
        401: {"model": ErrorEnvelope, "description": "Authentication failed"},
        403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
        429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
        500: {"model": ErrorEnvelope, "description": "Internal server error"},
    },
    tags=["Knowledge Bases"],
    operation_id="updateKnowledgeBase",
    summary="Update Knowledge Base",
    response_model_by_alias=True,
)
async def update_knowledge_base(
    implementation: Annotated[
        BaseKnowledgeBasesApi,
        Depends(get_knowledge_bases_api_implementation),
    ],
    kb_id: StrictStr = Path(..., description=""),
    knowledge_base_update: KnowledgeBaseUpdate = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> KnowledgeBaseResponse:
    return await implementation.update_knowledge_base(kb_id, knowledge_base_update)
