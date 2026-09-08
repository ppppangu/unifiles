"""FastAPI dependency providers for the system feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from unifiles_server_protocol.apis.system_api_base import BaseSystemApi

from .adapter import SystemAdapter
from .service import SystemService


def get_system_service() -> SystemService:
    return SystemService()


def provide_system_adapter(
    service: Annotated[SystemService, Depends(get_system_service)],
) -> BaseSystemApi:
    return SystemAdapter(service)
