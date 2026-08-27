# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import StrictStr
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.hybrid_search_request import HybridSearchRequest
from unifiles_server_protocol.models.search_request import SearchRequest
from unifiles_server_protocol.models.search_response import SearchResponse
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseSearchApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSearchApi.subclasses = BaseSearchApi.subclasses + (cls,)
    async def search_knowledge_base(
        self,
        kb_id: StrictStr,
        search_request: SearchRequest,
    ) -> SearchResponse:
        ...


    async def hybrid_search_knowledge_base(
        self,
        kb_id: StrictStr,
        hybrid_search_request: HybridSearchRequest,
    ) -> SearchResponse:
        ...
