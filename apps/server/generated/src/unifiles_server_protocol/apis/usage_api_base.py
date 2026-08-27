# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.usage_limits_response import UsageLimitsResponse
from unifiles_server_protocol.models.usage_stats_response import UsageStatsResponse
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseUsageApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseUsageApi.subclasses = BaseUsageApi.subclasses + (cls,)
    async def get_usage_stats(
        self,
    ) -> UsageStatsResponse:
        ...


    async def get_usage_limits(
        self,
    ) -> UsageLimitsResponse:
        ...
