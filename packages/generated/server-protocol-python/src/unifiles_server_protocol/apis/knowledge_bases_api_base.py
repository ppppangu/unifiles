# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

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

class BaseKnowledgeBasesApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseKnowledgeBasesApi.subclasses = BaseKnowledgeBasesApi.subclasses + (cls,)
    async def list_knowledge_bases(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> KnowledgeBaseListResponse:
        ...


    async def create_knowledge_base(
        self,
        knowledge_base_create: KnowledgeBaseCreate,
        idempotency_key: Optional[StrictStr],
    ) -> KnowledgeBaseResponse:
        ...


    async def get_knowledge_base(
        self,
        kb_id: StrictStr,
    ) -> KnowledgeBaseResponse:
        ...


    async def delete_knowledge_base(
        self,
        kb_id: StrictStr,
    ) -> DeletionResponse:
        ...


    async def update_knowledge_base(
        self,
        kb_id: StrictStr,
        knowledge_base_update: KnowledgeBaseUpdate,
    ) -> KnowledgeBaseResponse:
        ...
