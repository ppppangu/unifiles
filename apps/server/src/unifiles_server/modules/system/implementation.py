"""OpenAPI transport adapter for the system feature."""

from __future__ import annotations

from unifiles_server_protocol.apis.system_api_base import BaseSystemApi
from unifiles_server_protocol.models.health_details import HealthDetails
from unifiles_server_protocol.models.health_details_response import HealthDetailsResponse
from unifiles_server_protocol.models.health_response import HealthResponse
from unifiles_server_protocol.models.health_status import HealthStatus

from .service import SystemService


class SystemImplementation(BaseSystemApi):
    def __init__(self, service: SystemService) -> None:
        self._service = service

    async def get_health_details(self) -> HealthDetailsResponse:
        result = await self._service.get_health_details()
        return HealthDetailsResponse(
            data=HealthDetails(
                status=result.status,
                version=result.version,
                python_version=result.python_version,
                database=result.database,
            )
        )

    async def get_health(self) -> HealthResponse:
        result = await self._service.get_health()
        return HealthResponse(
            data=HealthStatus(
                status=result.status,
                version=result.version,
            )
        )

    async def get_versioned_health(self) -> HealthResponse:
        return await self.get_health()
