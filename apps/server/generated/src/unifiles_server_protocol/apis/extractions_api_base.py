# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.extraction_create import ExtractionCreate
from unifiles_server_protocol.models.extraction_list_response import ExtractionListResponse
from unifiles_server_protocol.models.extraction_response import ExtractionResponse
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseExtractionsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseExtractionsApi.subclasses = BaseExtractionsApi.subclasses + (cls,)
    async def list_file_extractions(
        self,
        file_id: StrictStr,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> ExtractionListResponse:
        ...


    async def create_extraction(
        self,
        extraction_create: ExtractionCreate,
        idempotency_key: Optional[StrictStr],
    ) -> ExtractionResponse:
        ...


    async def get_extraction(
        self,
        extraction_id: StrictStr,
    ) -> ExtractionResponse:
        ...
