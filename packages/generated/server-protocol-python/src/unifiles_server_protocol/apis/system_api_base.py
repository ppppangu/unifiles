# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.health_details_response import HealthDetailsResponse
from unifiles_server_protocol.models.health_response import HealthResponse


class BaseSystemApi(ABC):
    @abstractmethod
    async def get_versioned_health(
        self,
    ) -> HealthResponse:
        raise NotImplementedError


    @abstractmethod
    async def get_health_details(
        self,
    ) -> HealthDetailsResponse:
        raise NotImplementedError


    @abstractmethod
    async def get_health(
        self,
    ) -> HealthResponse:
        raise NotImplementedError
