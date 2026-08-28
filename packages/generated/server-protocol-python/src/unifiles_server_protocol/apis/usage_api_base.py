# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.usage_limits_response import UsageLimitsResponse
from unifiles_server_protocol.models.usage_stats_response import UsageStatsResponse


class BaseUsageApi(ABC):
    @abstractmethod
    async def get_usage_stats(
        self,
    ) -> UsageStatsResponse:
        raise NotImplementedError


    @abstractmethod
    async def get_usage_limits(
        self,
    ) -> UsageLimitsResponse:
        raise NotImplementedError
