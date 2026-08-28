# coding: utf-8

from abc import ABC, abstractmethod
from typing import Dict, List  # noqa: F401

from pydantic import Field, StrictBytes, StrictStr
from typing import Optional, Tuple, Union
from typing_extensions import Annotated
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.file_list_response import FileListResponse
from unifiles_server_protocol.models.file_response import FileResponse
from unifiles_server_protocol.models.supported_file_types_response import SupportedFileTypesResponse
from fastapi import File, UploadFile


class BaseFilesApi(ABC):
    @abstractmethod
    async def list_supported_file_types(
        self,
    ) -> SupportedFileTypesResponse:
        raise NotImplementedError


    @abstractmethod
    async def list_files(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
        tags: Optional[StrictStr],
        content_type: Optional[StrictStr],
        sort_by: Optional[StrictStr],
        order: Optional[StrictStr],
    ) -> FileListResponse:
        raise NotImplementedError


    @abstractmethod
    async def upload_file(
        self,
        file: UploadFile,
        idempotency_key: Optional[StrictStr],
        metadata: Optional[StrictStr],
        tags: Optional[StrictStr],
    ) -> FileResponse:
        raise NotImplementedError


    @abstractmethod
    async def get_file(
        self,
        file_id: StrictStr,
    ) -> FileResponse:
        raise NotImplementedError


    @abstractmethod
    async def delete_file(
        self,
        file_id: StrictStr,
    ) -> DeletionResponse:
        raise NotImplementedError


    @abstractmethod
    async def download_file(
        self,
        file_id: StrictStr,
    ) -> bytes:
        raise NotImplementedError
