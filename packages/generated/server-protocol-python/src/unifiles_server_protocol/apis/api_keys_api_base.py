# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.api_key_create import APIKeyCreate
from unifiles_server_protocol.models.api_key_list_response import APIKeyListResponse
from unifiles_server_protocol.models.api_key_response import APIKeyResponse
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope


class BaseAPIKeysApi(ABC):
    @abstractmethod
    async def list_api_keys(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> APIKeyListResponse:
        raise NotImplementedError


    @abstractmethod
    async def create_api_key(
        self,
        api_key_create: APIKeyCreate,
        idempotency_key: Optional[StrictStr],
    ) -> APIKeyResponse:
        raise NotImplementedError


    @abstractmethod
    async def revoke_api_key(
        self,
        key_id: StrictStr,
    ) -> DeletionResponse:
        raise NotImplementedError
