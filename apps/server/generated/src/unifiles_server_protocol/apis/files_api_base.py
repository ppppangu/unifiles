# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictBytes, StrictStr
from typing import Optional, Tuple, Union
from typing_extensions import Annotated
from unifiles_server_protocol.models.deletion_response import DeletionResponse
from unifiles_server_protocol.models.error_envelope import ErrorEnvelope
from unifiles_server_protocol.models.file_list_response import FileListResponse
from unifiles_server_protocol.models.file_response import FileResponse
from unifiles_server_protocol.models.supported_file_types_response import SupportedFileTypesResponse
from fastapi import File, UploadFile
from unifiles_server_protocol.security_api import get_token_BearerAuth

class BaseFilesApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseFilesApi.subclasses = BaseFilesApi.subclasses + (cls,)
    async def list_supported_file_types(
        self,
    ) -> SupportedFileTypesResponse:
        ...


    async def list_files(
        self,
        limit: Optional[Annotated[int, Field(le=100, strict=True, ge=1)]],
        offset: Optional[Annotated[int, Field(strict=True, ge=0)]],
        tags: Optional[StrictStr],
        content_type: Optional[StrictStr],
        sort_by: Optional[StrictStr],
        order: Optional[StrictStr],
    ) -> FileListResponse:
        ...


    async def upload_file(
        self,
        file: UploadFile,
        idempotency_key: Optional[StrictStr],
        metadata: Optional[StrictStr],
        tags: Optional[StrictStr],
    ) -> FileResponse:
        ...


    async def get_file(
        self,
        file_id: StrictStr,
    ) -> FileResponse:
        ...


    async def delete_file(
        self,
        file_id: StrictStr,
    ) -> DeletionResponse:
        ...


    async def download_file(
        self,
        file_id: StrictStr,
    ) -> bytes:
        ...
