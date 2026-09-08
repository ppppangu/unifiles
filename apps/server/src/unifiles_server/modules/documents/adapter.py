"""OpenAPI transport adapter for indexed documents."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi
from unifiles_server_protocol.models.document_create import DocumentCreate

from ...shared.auth import current_context
from ...shared.responses import success
from .service import run_indexing


class DocumentsAdapter(BaseDocumentsApi):
    async def create_document(
        self, kb_id: str, document_create: DocumentCreate, idempotency_key: str | None
    ) -> Any:
        request, principal, database = current_context()
        operation = f"documents.create:{kb_id}"
        cached = database.idempotent_get(principal["user_id"], idempotency_key, operation)
        if cached:
            return success(cached)
        resource = database.create_document(
            principal["user_id"],
            kb_id,
            document_create.file_id,
            document_create.title,
            document_create.metadata or {},
        )
        public = {
            key: value for key, value in resource.items() if key not in {"extraction_id", "user_id"}
        }
        database.idempotent_put(principal["user_id"], idempotency_key, operation, public)
        request.app.state.executor.submit(
            run_indexing, database, principal["user_id"], kb_id, resource["id"]
        )
        return success(public)

    async def list_documents(self, kb_id: str, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(
            database.list_documents(principal["user_id"], kb_id, limit or 50, offset or 0)
        )

    async def get_document(self, kb_id: str, document_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.document(principal["user_id"], kb_id, document_id))

    async def delete_document(self, kb_id: str, document_id: str) -> Any:
        _, principal, database = current_context()
        database.delete_document(principal["user_id"], kb_id, document_id)
        return success({"id": document_id, "deleted": True})
