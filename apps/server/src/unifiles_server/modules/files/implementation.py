"""OpenAPI transport adapter for the files feature."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from fastapi.responses import FileResponse
from unifiles_server_protocol.apis.files_api_base import BaseFilesApi
from unifiles_server_protocol.models.supported_file_types import SupportedFileTypes
from unifiles_server_protocol.models.supported_file_types_response import (
    SupportedFileTypesResponse,
)

from ...auth import add_background_task, current_context
from ...errors import APIError
from ...implementation.handlers import success
from ...services import dispatch_event
from ...store import identifier
from .service import FilesService


def parse_object(value: str, field: str) -> dict[str, Any]:
    if len(value.encode()) > 64 * 1024:
        raise APIError(422, "VALIDATION_ERROR", f"{field} exceeds 64 KiB")
    try:
        result = json.loads(value)
    except ValueError as error:
        raise APIError(422, "VALIDATION_ERROR", f"{field} must be valid JSON") from error
    if not isinstance(result, dict):
        raise APIError(422, "VALIDATION_ERROR", f"{field} must be a JSON object")
    return result


def parse_tags(value: str) -> list[str]:
    try:
        result = json.loads(value)
        if isinstance(result, list):
            tags = [str(item) for item in result]
            if len(tags) > 100 or any(len(item) > 100 for item in tags):
                raise APIError(422, "VALIDATION_ERROR", "tags exceed the configured limits")
            return list(dict.fromkeys(tags))
    except ValueError:
        pass
    tags = [item.strip() for item in value.split(",") if item.strip()]
    if len(tags) > 100 or any(len(item) > 100 for item in tags):
        raise APIError(422, "VALIDATION_ERROR", "tags exceed the configured limits")
    return list(dict.fromkeys(tags))


def sanitize_filename(value: str) -> str:
    name = Path(value).name
    name = re.sub(r"[^\w.()\-\u3400-\u9fff ]+", "_", name).strip(". ")
    if not name:
        raise APIError(422, "INVALID_FILENAME", "The filename is invalid")
    if len(name.encode()) > 240:
        raise APIError(422, "INVALID_FILENAME", "The filename exceeds 240 bytes")
    return name


class FilesImplementation(BaseFilesApi):
    def __init__(self, service: FilesService) -> None:
        self._service = service

    async def list_supported_file_types(self) -> SupportedFileTypesResponse:
        result = self._service.list_supported_file_types()
        return SupportedFileTypesResponse(
            data=SupportedFileTypes(
                document_types=list(result.document_types),
                image_types=list(result.image_types),
                all_types=list(result.all_types),
            )
        )

    async def upload_file(
        self,
        file: UploadFile,
        idempotency_key: str | None,
        metadata: str | None,
        tags: str | None,
    ) -> Any:
        request, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "files.create")
        if cached:
            return success(cached)
        content = await file.read()
        if not content:
            raise APIError(422, "EMPTY_FILE", "The uploaded file is empty")
        settings = request.app.state.settings
        if len(content) > settings.max_file_size_bytes:
            raise APIError(413, "FILE_TOO_LARGE", "The uploaded file exceeds the configured limit")
        usage = database.usage(principal["user_id"])
        if usage["storage"]["used_bytes"] + len(content) > settings.storage_limit_bytes:
            raise APIError(403, "QUOTA_EXCEEDED", "Storage quota exceeded")
        filename = sanitize_filename(file.filename or "")
        file_id = identifier("file")
        directory = settings.files_dir / principal["user_id"] / file_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_bytes(content)
        resource = database.insert_file(
            file_id=file_id,
            user_id=principal["user_id"],
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            size=len(content),
            metadata=parse_object(metadata or "{}", "metadata"),
            tags=parse_tags(tags or "[]"),
            storage_path=str(path),
        )
        database.idempotent_put(principal["user_id"], idempotency_key, "files.create", resource)
        add_background_task(
            dispatch_event,
            database,
            principal["user_id"],
            "file.uploaded",
            {"file_id": file_id, "filename": filename, "size": len(content)},
        )
        return success(resource)

    async def list_files(
        self,
        limit: int | None,
        offset: int | None,
        tags: str | None,
        content_type: str | None,
        sort_by: str | None,
        order: str | None,
    ) -> Any:
        _, principal, database = current_context()
        return success(
            database.list_files(
                principal["user_id"],
                limit=limit or 50,
                offset=offset or 0,
                tags=parse_tags(tags) if tags else None,
                content_type=content_type,
                sort_by=sort_by or "created_at",
                order=order or "desc",
            )
        )

    async def get_file(self, file_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.file(principal["user_id"], file_id))

    async def download_file(self, file_id: str) -> Any:
        _, principal, database = current_context()
        resource = database.file(principal["user_id"], file_id, internal=True)
        return FileResponse(
            resource["storage_path"],
            filename=resource["filename"],
            media_type=resource["content_type"],
        )

    async def delete_file(self, file_id: str) -> Any:
        _, principal, database = current_context()
        path = Path(database.delete_file(principal["user_id"], file_id))
        if path.exists():
            path.unlink()
        add_background_task(
            dispatch_event,
            database,
            principal["user_id"],
            "file.deleted",
            {"file_id": file_id},
        )
        return success({"id": file_id, "deleted": True})
