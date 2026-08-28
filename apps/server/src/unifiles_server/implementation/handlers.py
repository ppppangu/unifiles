"""Legacy business adapters awaiting migration into feature modules.

This module is handwritten. Regeneration only changes ``unifiles_server_protocol``;
the generated route layer receives these implementations through FastAPI dependencies.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, HttpUrl, TypeAdapter, ValidationError
from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi
from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi
from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi
from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi
from unifiles_server_protocol.apis.search_api_base import BaseSearchApi
from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi
from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi
from unifiles_server_protocol.models.api_key_create import APIKeyCreate
from unifiles_server_protocol.models.document_create import DocumentCreate
from unifiles_server_protocol.models.extraction_create import ExtractionCreate
from unifiles_server_protocol.models.hybrid_search_request import HybridSearchRequest
from unifiles_server_protocol.models.knowledge_base_create import KnowledgeBaseCreate
from unifiles_server_protocol.models.knowledge_base_update import KnowledgeBaseUpdate
from unifiles_server_protocol.models.search_request import SearchRequest
from unifiles_server_protocol.models.webhook_create import WebhookCreate
from unifiles_server_protocol.models.webhook_update import WebhookUpdate

from ..auth import current_context
from ..errors import APIError
from ..services import run_extraction, run_indexing, search


def success(data: Any) -> dict[str, Any]:
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    return {"success": True, "data": data}


def model_payload(model: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]:
    return model.model_dump(
        mode="json",
        exclude={"additional_properties"},
        exclude_unset=exclude_unset,
    )


def normalize_chunking(value: Any | None) -> dict[str, Any]:
    result: dict[str, Any]
    if value is None:
        result = {"type": "semantic", "chunk_size": 512, "overlap": 50}
    elif isinstance(value, BaseModel):
        result = value.model_dump(mode="json", exclude={"additional_properties"})
    else:
        result = dict(value)
    chunk_size = int(result.get("chunk_size", 512))
    overlap = int(result.get("overlap", 50))
    if overlap >= chunk_size:
        raise APIError(422, "VALIDATION_ERROR", "overlap must be smaller than chunk_size")
    return {**result, "chunk_size": chunk_size, "overlap": overlap}


class ExtractionsImplementation(BaseExtractionsApi):
    async def list_file_extractions(
        self, file_id: str, limit: int | None, offset: int | None
    ) -> Any:
        _, principal, database = current_context()
        return success(
            database.list_extractions(principal["user_id"], file_id, limit or 50, offset or 0)
        )

    async def create_extraction(
        self, extraction_create: ExtractionCreate, idempotency_key: str | None
    ) -> Any:
        request, principal, database = current_context()
        cached = database.idempotent_get(
            principal["user_id"], idempotency_key, "extractions.create"
        )
        if cached:
            return success(cached)
        options = (
            extraction_create.options.model_dump(mode="json", exclude_none=True)
            if extraction_create.options is not None
            else {}
        )
        resource = database.create_extraction(
            principal["user_id"],
            extraction_create.file_id,
            extraction_create.mode or "normal",
            options,
        )
        database.idempotent_put(
            principal["user_id"], idempotency_key, "extractions.create", resource
        )
        request.app.state.executor.submit(
            run_extraction, database, principal["user_id"], resource["id"]
        )
        return success(resource)

    async def get_extraction(self, extraction_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.extraction(principal["user_id"], extraction_id))


class KnowledgeBasesImplementation(BaseKnowledgeBasesApi):
    async def create_knowledge_base(
        self, knowledge_base_create: KnowledgeBaseCreate, idempotency_key: str | None
    ) -> Any:
        request, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "kb.create")
        if cached:
            return success(cached)
        if (
            database.usage(principal["user_id"])["knowledge_bases"]["used"]
            >= request.app.state.settings.knowledge_base_limit
        ):
            raise APIError(403, "QUOTA_EXCEEDED", "Knowledge base quota exceeded")
        payload = model_payload(knowledge_base_create)
        payload["chunking_strategy"] = normalize_chunking(knowledge_base_create.chunking_strategy)
        payload["metadata"] = payload.get("metadata") or {}
        resource = database.create_kb(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "kb.create", resource)
        return success(resource)

    async def list_knowledge_bases(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_kbs(principal["user_id"], limit or 50, offset or 0))

    async def get_knowledge_base(self, kb_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.kb(principal["user_id"], kb_id))

    async def update_knowledge_base(
        self, kb_id: str, knowledge_base_update: KnowledgeBaseUpdate
    ) -> Any:
        _, principal, database = current_context()
        fields = knowledge_base_update.model_fields_set - {"additional_properties"}
        if not fields:
            raise APIError(422, "VALIDATION_ERROR", "At least one field is required")
        changes = model_payload(knowledge_base_update, exclude_unset=True)
        if "chunking_strategy" in changes:
            if knowledge_base_update.chunking_strategy is None:
                raise APIError(422, "VALIDATION_ERROR", "chunking_strategy cannot be null")
            changes["chunking_strategy"] = normalize_chunking(
                knowledge_base_update.chunking_strategy
            )
        return success(database.update_kb(principal["user_id"], kb_id, changes))

    async def delete_knowledge_base(self, kb_id: str) -> Any:
        _, principal, database = current_context()
        database.delete_kb(principal["user_id"], kb_id)
        return success({"id": kb_id, "deleted": True})


class DocumentsImplementation(BaseDocumentsApi):
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


class SearchImplementation(BaseSearchApi):
    async def search_knowledge_base(self, kb_id: str, search_request: SearchRequest) -> Any:
        _, principal, database = current_context()
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                search_request.query,
                top_k=search_request.top_k or 5,
                threshold=search_request.threshold or 0,
                metadata_filter=search_request.filter,
            )
        )

    async def hybrid_search_knowledge_base(
        self, kb_id: str, hybrid_search_request: HybridSearchRequest
    ) -> Any:
        _, principal, database = current_context()
        vector_weight = float(hybrid_search_request.vector_weight or 0)
        keyword_weight = float(hybrid_search_request.keyword_weight or 0)
        if vector_weight + keyword_weight <= 0:
            raise APIError(422, "VALIDATION_ERROR", "At least one search weight must be positive")
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                hybrid_search_request.query,
                top_k=hybrid_search_request.top_k or 5,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
        )


class WebhooksImplementation(BaseWebhooksApi):
    async def create_webhook(
        self, webhook_create: WebhookCreate, idempotency_key: str | None
    ) -> Any:
        _, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "webhooks.create")
        if cached:
            return success(cached)
        try:
            url = str(TypeAdapter(HttpUrl).validate_python(webhook_create.url))
        except ValidationError as error:
            raise APIError(422, "VALIDATION_ERROR", "url must be a valid HTTP URL") from error
        payload = model_payload(webhook_create)
        payload["url"] = url
        resource = database.create_webhook(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "webhooks.create", resource)
        return success(resource)

    async def list_webhooks(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_webhooks(principal["user_id"], limit or 50, offset or 0))

    async def get_webhook(self, webhook_id: str) -> Any:
        _, principal, database = current_context()
        return success(database.webhook(principal["user_id"], webhook_id))

    async def update_webhook(self, webhook_id: str, webhook_update: WebhookUpdate) -> Any:
        _, principal, database = current_context()
        changes = model_payload(webhook_update, exclude_unset=True)
        if "url" in changes and webhook_update.url is not None:
            try:
                changes["url"] = str(TypeAdapter(HttpUrl).validate_python(webhook_update.url))
            except ValidationError as error:
                raise APIError(422, "VALIDATION_ERROR", "url must be a valid HTTP URL") from error
        if "events" in changes and webhook_update.events is None:
            raise APIError(422, "VALIDATION_ERROR", "events cannot be null")
        return success(database.update_webhook(principal["user_id"], webhook_id, changes))

    async def delete_webhook(self, webhook_id: str) -> Any:
        _, principal, database = current_context()
        database.delete_webhook(principal["user_id"], webhook_id)
        return success({"id": webhook_id, "deleted": True})


class APIKeysImplementation(BaseAPIKeysApi):
    async def create_api_key(
        self, api_key_create: APIKeyCreate, idempotency_key: str | None
    ) -> Any:
        _, principal, database = current_context()
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "api-keys.create")
        if cached:
            return success(cached)
        payload = model_payload(api_key_create)
        payload["scopes"] = payload.get("scopes") or ["*"]
        resource = database.create_api_key(principal["user_id"], payload)
        database.idempotent_put(principal["user_id"], idempotency_key, "api-keys.create", resource)
        return success(resource)

    async def list_api_keys(self, limit: int | None, offset: int | None) -> Any:
        _, principal, database = current_context()
        return success(database.list_api_keys(principal["user_id"], limit or 50, offset or 0))

    async def revoke_api_key(self, key_id: str) -> Any:
        _, principal, database = current_context()
        database.revoke_api_key(principal["user_id"], key_id)
        return success({"id": key_id, "deleted": True})


class UsageImplementation(BaseUsageApi):
    async def get_usage_stats(self) -> Any:
        _, principal, database = current_context()
        return success(database.usage(principal["user_id"]))

    async def get_usage_limits(self) -> Any:
        request, _, _ = current_context()
        settings = request.app.state.settings
        return success(
            {
                "api_calls": {"limit": None, "window": "unlimited"},
                "storage": {"limit_bytes": settings.storage_limit_bytes},
                "files": {"max_file_size_bytes": settings.max_file_size_bytes},
            }
        )
