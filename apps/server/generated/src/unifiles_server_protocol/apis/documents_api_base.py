# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.document_create import DocumentCreate
from unifiles_server_protocol.models.document_list_response import DocumentListResponse
from unifiles_server_protocol.models.document_response import DocumentResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseDocumentsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDocumentsApi.subclasses = BaseDocumentsApi.subclasses + (cls,)
    async def list_documents(
        self,
        kb_id: StrictStr,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> DocumentListResponse:
        ...


    async def create_document(
        self,
        kb_id: StrictStr,
        document_create: DocumentCreate,
        idempotency_key: Optional[StrictStr],
    ) -> DocumentResponse:
        ...


    async def get_document(
        self,
        kb_id: StrictStr,
        document_id: StrictStr,
    ) -> DocumentResponse:
        ...


    async def delete_document(
        self,
        kb_id: StrictStr,
        document_id: StrictStr,
    ) -> DeletionResponse:
        ...
