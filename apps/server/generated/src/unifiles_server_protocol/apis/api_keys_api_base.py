# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated
from unifiles_server_protocol.models.api_key_create import APIKeyCreate
from unifiles_server_protocol.models.api_key_list_response import APIKeyListResponse
from unifiles_server_protocol.models.api_key_response import APIKeyResponse
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseAPIKeysApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAPIKeysApi.subclasses = BaseAPIKeysApi.subclasses + (cls,)
    async def list_api_keys(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
    ) -> APIKeyListResponse:
        ...


    async def create_api_key(
        self,
        api_key_create: APIKeyCreate,
        idempotency_key: Optional[StrictStr],
    ) -> APIKeyResponse:
        ...


    async def revoke_api_key(
        self,
        key_id: StrictStr,
    ) -> DeletionResponse:
        ...
