"""System health use cases independent of HTTP transport."""

from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthResult:
    status: str
    version: str


@dataclass(frozen=True)
class HealthDetailsResult(HealthResult):
    python_version: str
    database: str


class SystemService:
    async def get_health(self) -> HealthResult:
        return HealthResult(status="ok", version="1.0.0")

    async def get_health_details(self) -> HealthDetailsResult:
        return HealthDetailsResult(
            status="ok",
            version="1.0.0",
            python_version=platform.python_version(),
            database="ok",
        )
