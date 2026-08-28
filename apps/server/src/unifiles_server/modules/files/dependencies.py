"""FastAPI dependency providers for the files feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from unifiles_server_protocol.apis.files_api_base import BaseFilesApi

from .implementation import FilesImplementation
from .service import FilesService


def get_files_service() -> FilesService:
    return FilesService()


def get_files_api_implementation(
    service: Annotated[FilesService, Depends(get_files_service)],
) -> BaseFilesApi:
    return FilesImplementation(service)
