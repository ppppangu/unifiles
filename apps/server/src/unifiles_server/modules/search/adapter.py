"""OpenAPI transport adapter for knowledge-base search."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.search_api_base import BaseSearchApi
from unifiles_server_protocol.models.hybrid_search_request import HybridSearchRequest
from unifiles_server_protocol.models.search_request import SearchRequest

from ...shared.auth import current_context
from ...shared.errors import APIError
from ...shared.responses import success
from .service import search


class SearchAdapter(BaseSearchApi):
    async def search_knowledge_base(self, kb_id: str, search_request: SearchRequest) -> Any:
        _, principal, database = current_context()
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                search_request.query,
                top_k=search_request.top_k or 5,
                threshold=search_request.threshold or 0,
                metadata_filter=search_request.filter,
            )
        )

    async def hybrid_search_knowledge_base(
        self, kb_id: str, hybrid_search_request: HybridSearchRequest
    ) -> Any:
        _, principal, database = current_context()
        vector_weight = float(hybrid_search_request.vector_weight or 0)
        keyword_weight = float(hybrid_search_request.keyword_weight or 0)
        if vector_weight + keyword_weight <= 0:
            raise APIError(422, "VALIDATION_ERROR", "At least one search weight must be positive")
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                hybrid_search_request.query,
                top_k=hybrid_search_request.top_k or 5,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
        )
