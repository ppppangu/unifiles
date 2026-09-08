# coding: utf-8

from collections.abc import Callable
from typing import Annotated, Dict, List, TypeAlias  # noqa: F401

from unifiles_server_protocol.apis.search_api_base import BaseSearchApi

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
from pydantic import StrictStr
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.hybrid_search_request import HybridSearchRequest
from unifiles_server_protocol.models.search_request import SearchRequest
from unifiles_server_protocol.models.search_response import SearchResponse
from unifiles_server_protocol.security_api import SecurityProvider

AdapterProvider: TypeAlias = Callable[..., BaseSearchApi]


def create_router(
    get_adapter: AdapterProvider,
    get_token_BearerAuth: SecurityProvider,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/v1/knowledge-bases/{kb_id}/search",
        status_code=200,
        responses={
            200: {"model": SearchResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Search"],
        operation_id="searchKnowledgeBase",
        summary="Semantic Search",
        response_model_by_alias=True,
    )
    async def search_knowledge_base(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseSearchApi,
            Depends(get_adapter),
        ],
        kb_id: StrictStr = Path(..., description=""),
        search_request: SearchRequest = Body(None, description=""),
    ) -> SearchResponse:
        return await adapter.search_knowledge_base(kb_id, search_request)

    @router.post(
        "/v1/knowledge-bases/{kb_id}/hybrid-search",
        status_code=200,
        responses={
            200: {"model": SearchResponse, "description": "Successful Response"},
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
        tags=["Search"],
        operation_id="hybridSearchKnowledgeBase",
        summary="Hybrid Search",
        response_model_by_alias=True,
    )
    async def hybrid_search_knowledge_base(
        token_BearerAuth: Annotated[
            TokenModel,
            Security(
                get_token_BearerAuth
            ),
        ],
        adapter: Annotated[
            BaseSearchApi,
            Depends(get_adapter),
        ],
        kb_id: StrictStr = Path(..., description=""),
        hybrid_search_request: HybridSearchRequest = Body(None, description=""),
    ) -> SearchResponse:
        return await adapter.hybrid_search_knowledge_base(kb_id, hybrid_search_request)
    return router
