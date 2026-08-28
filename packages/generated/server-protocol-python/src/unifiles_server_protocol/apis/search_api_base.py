# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from pydantic import StrictStr
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.hybrid_search_request import HybridSearchRequest
from unifiles_server_protocol.models.search_request import SearchRequest
from unifiles_server_protocol.models.search_response import SearchResponse


class BaseSearchApi(ABC):
    @abstractmethod
    async def search_knowledge_base(
        self,
        kb_id: StrictStr,
        search_request: SearchRequest,
    ) -> SearchResponse:
        raise NotImplementedError


    @abstractmethod
    async def hybrid_search_knowledge_base(
        self,
        kb_id: StrictStr,
        hybrid_search_request: HybridSearchRequest,
    ) -> SearchResponse:
        raise NotImplementedError
