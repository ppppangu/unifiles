# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.extraction_create import ExtractionCreate
from unifiles_server_protocol.models.extraction_list_response import ExtractionListResponse
from unifiles_server_protocol.models.extraction_response import ExtractionResponse


class BaseExtractionsApi(ABC):
    @abstractmethod
    async def list_file_extractions(
        self,
        file_id: StrictStr,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> ExtractionListResponse:
        raise NotImplementedError


    @abstractmethod
    async def create_extraction(
        self,
        extraction_create: ExtractionCreate,
        idempotency_key: Optional[StrictStr],
    ) -> ExtractionResponse:
        raise NotImplementedError


    @abstractmethod
    async def get_extraction(
        self,
        extraction_id: StrictStr,
    ) -> ExtractionResponse:
        raise NotImplementedError
