# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.health_response import HealthResponse


class BaseSystemApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSystemApi.subclasses = BaseSystemApi.subclasses + (cls,)
    async def get_versioned_health(
        self,
    ) -> HealthResponse:
        ...


    async def get_health(
        self,
    ) -> HealthResponse:
        ...
