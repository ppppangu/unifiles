import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .errors import APIError, install_error_handlers
from .models import (
    APIKeyCreate,
    APIKeyResource,
    DeletionResult,
    DocumentCreate,
    DocumentResource,
    ErrorEnvelope,
    ExtractionCreate,
    ExtractionResource,
    FileResource,
    HybridSearchRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResource,
    KnowledgeBaseUpdate,
    ListData,
    SearchRequest,
    SearchResults,
    SuccessEnvelope,
    SupportedFileTypes,
    WebhookCreate,
    WebhookResource,
    WebhookUpdate,
)
from .services import dispatch_event, run_extraction, run_indexing, search
from .settings import Settings
from .settings import settings as default_settings
from .store import Store, identifier


def success(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    return {"success": True, "data": data}


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


def create_app(config: Settings | None = None) -> FastAPI:
    current = config or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = Store(current)
        app.state.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="unifiles-task")
        for extraction in app.state.store.pending_extractions():
            app.state.executor.submit(
                run_extraction, app.state.store, extraction["user_id"], extraction["id"]
            )
        for document in app.state.store.pending_documents():
            app.state.executor.submit(
                run_indexing,
                app.state.store,
                document["user_id"],
                document["kb_id"],
                document["id"],
            )
        yield
        app.state.executor.shutdown(wait=True, cancel_futures=False)
        app.state.store.close()

    app = FastAPI(
        title="Unifiles API",
        version="1.0.0",
        description="Self-hosted document processing infrastructure",
        lifespan=lifespan,
        responses={
            400: {"model": ErrorEnvelope, "description": "Invalid request"},
            401: {"model": ErrorEnvelope, "description": "Authentication failed"},
            403: {"model": ErrorEnvelope, "description": "Permission or quota denied"},
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            409: {"model": ErrorEnvelope, "description": "Resource state conflict"},
            422: {"model": ErrorEnvelope, "description": "Validation or processing error"},
            429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
    )
    app.state.settings = current
    cors_origins = [item.strip() for item in current.cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    install_error_handlers(app)

    def store(request: Request) -> Store:
        return request.app.state.store

    bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")

    def principal(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        database: Store = Depends(store),
    ) -> dict[str, Any]:
        if not credentials or credentials.scheme.lower() != "bearer":
            raise APIError(401, "MISSING_API_KEY", "Authorization: Bearer <api-key> is required")
        authenticated = database.authenticate(credentials.credentials)
        parts = request.url.path.removeprefix("/v1/").split("/")
        domain = {
            "knowledge-bases": "kb",
            "api-keys": "api_keys",
        }.get(parts[0], parts[0])
        action = (
            "read"
            if request.method == "GET" or parts[-1] in {"search", "hybrid-search"}
            else "write"
        )
        scopes = set(authenticated["scopes"])
        if not ({"*", f"{domain}:*", f"{domain}:{action}"} & scopes):
            raise APIError(
                403,
                "INSUFFICIENT_SCOPE",
                f"API key requires {domain}:{action}",
                details={"required_scope": f"{domain}:{action}"},
            )
        return authenticated

    Principal = Annotated[dict[str, Any], Depends(principal)]
    Database = Annotated[Store, Depends(store)]

    @app.get("/health", response_model=SuccessEnvelope[dict[str, Any]], tags=["System"])
    @app.get("/v1/health", response_model=SuccessEnvelope[dict[str, Any]], tags=["System"])
    def health() -> dict[str, Any]:
        return success({"status": "ok", "version": "1.0.0"})

    @app.get(
        "/v1/files/types",
        response_model=SuccessEnvelope[SupportedFileTypes],
        tags=["Files"],
    )
    def supported_types(_: Principal) -> dict[str, Any]:
        document = [".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".xml"]
        images = [".png", ".jpg", ".jpeg", ".tiff", ".webp"]
        return success(
            {"document_types": document, "image_types": images, "all_types": document + images}
        )

    @app.post(
        "/v1/files",
        status_code=status.HTTP_201_CREATED,
        response_model=SuccessEnvelope[FileResource],
        tags=["Files"],
    )
    async def upload_file(
        background: BackgroundTasks,
        request: Request,
        principal: Principal,
        database: Database,
        file: UploadFile = File(...),
        metadata: str = Form("{}"),
        tags: str = Form("[]"),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "files.create")
        if cached:
            return success(cached)
        content = await file.read()
        if not content:
            raise APIError(422, "EMPTY_FILE", "The uploaded file is empty")
        if len(content) > current.max_file_size_bytes:
            raise APIError(413, "FILE_TOO_LARGE", "The uploaded file exceeds the configured limit")
        usage = database.usage(principal["user_id"])
        if usage["storage"]["used_bytes"] + len(content) > current.storage_limit_bytes:
            raise APIError(403, "QUOTA_EXCEEDED", "Storage quota exceeded")
        filename = sanitize_filename(file.filename or "")
        file_id = identifier("file")
        directory = current.files_dir / principal["user_id"] / file_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_bytes(content)
        resource = database.insert_file(
            file_id=file_id,
            user_id=principal["user_id"],
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            size=len(content),
            metadata=parse_object(metadata, "metadata"),
            tags=parse_tags(tags),
            storage_path=str(path),
        )
        database.idempotent_put(principal["user_id"], idempotency_key, "files.create", resource)
        background.add_task(
            dispatch_event,
            database,
            principal["user_id"],
            "file.uploaded",
            {"file_id": file_id, "filename": filename, "size": len(content)},
        )
        return success(resource)

    @app.get(
        "/v1/files",
        response_model=SuccessEnvelope[ListData[FileResource]],
        tags=["Files"],
    )
    def list_files(
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        tags: str | None = None,
        content_type: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> dict[str, Any]:
        return success(
            database.list_files(
                principal["user_id"],
                limit=limit,
                offset=offset,
                tags=parse_tags(tags) if tags else None,
                content_type=content_type,
                sort_by=sort_by,
                order=order,
            )
        )

    @app.get(
        "/v1/files/{file_id}/extractions",
        response_model=SuccessEnvelope[ListData[ExtractionResource]],
        tags=["Extractions"],
    )
    def file_extractions(
        file_id: str,
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return success(database.list_extractions(principal["user_id"], file_id, limit, offset))

    @app.get("/v1/files/{file_id}", response_model=SuccessEnvelope[FileResource], tags=["Files"])
    def get_file(file_id: str, principal: Principal, database: Database) -> dict[str, Any]:
        return success(database.file(principal["user_id"], file_id))

    @app.get("/v1/files/{file_id}/download", response_class=FileResponse, tags=["Files"])
    def download_file(file_id: str, principal: Principal, database: Database) -> FileResponse:
        resource = database.file(principal["user_id"], file_id, internal=True)
        return FileResponse(
            resource["storage_path"],
            filename=resource["filename"],
            media_type=resource["content_type"],
        )

    @app.delete(
        "/v1/files/{file_id}",
        response_model=SuccessEnvelope[DeletionResult],
        tags=["Files"],
    )
    def delete_file(
        file_id: str,
        background: BackgroundTasks,
        principal: Principal,
        database: Database,
    ) -> dict[str, Any]:
        path = Path(database.delete_file(principal["user_id"], file_id))
        if path.exists():
            path.unlink()
        background.add_task(
            dispatch_event,
            database,
            principal["user_id"],
            "file.deleted",
            {"file_id": file_id},
        )
        return success({"id": file_id, "deleted": True})

    @app.post(
        "/v1/extractions",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=SuccessEnvelope[ExtractionResource],
        tags=["Extractions"],
    )
    def create_extraction(
        payload: ExtractionCreate,
        request: Request,
        principal: Principal,
        database: Database,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        cached = database.idempotent_get(
            principal["user_id"], idempotency_key, "extractions.create"
        )
        if cached:
            return success(cached)
        resource = database.create_extraction(
            principal["user_id"], payload.file_id, payload.mode, payload.options
        )
        database.idempotent_put(
            principal["user_id"], idempotency_key, "extractions.create", resource
        )
        request.app.state.executor.submit(
            run_extraction, database, principal["user_id"], resource["id"]
        )
        return success(resource)

    @app.get(
        "/v1/extractions/{extraction_id}",
        response_model=SuccessEnvelope[ExtractionResource],
        tags=["Extractions"],
    )
    def get_extraction(
        extraction_id: str, principal: Principal, database: Database
    ) -> dict[str, Any]:
        return success(database.extraction(principal["user_id"], extraction_id))

    @app.post(
        "/v1/knowledge-bases",
        status_code=status.HTTP_201_CREATED,
        response_model=SuccessEnvelope[KnowledgeBaseResource],
        tags=["Knowledge Bases"],
    )
    def create_knowledge_base(
        payload: KnowledgeBaseCreate,
        principal: Principal,
        database: Database,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "kb.create")
        if cached:
            return success(cached)
        if (
            database.usage(principal["user_id"])["knowledge_bases"]["used"]
            >= current.knowledge_base_limit
        ):
            raise APIError(403, "QUOTA_EXCEEDED", "Knowledge base quota exceeded")
        resource = database.create_kb(principal["user_id"], payload.model_dump())
        database.idempotent_put(principal["user_id"], idempotency_key, "kb.create", resource)
        return success(resource)

    @app.get(
        "/v1/knowledge-bases",
        response_model=SuccessEnvelope[ListData[KnowledgeBaseResource]],
        tags=["Knowledge Bases"],
    )
    def list_knowledge_bases(
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return success(database.list_kbs(principal["user_id"], limit, offset))

    @app.get(
        "/v1/knowledge-bases/{kb_id}",
        response_model=SuccessEnvelope[KnowledgeBaseResource],
        tags=["Knowledge Bases"],
    )
    def get_knowledge_base(kb_id: str, principal: Principal, database: Database) -> dict[str, Any]:
        return success(database.kb(principal["user_id"], kb_id))

    @app.patch(
        "/v1/knowledge-bases/{kb_id}",
        response_model=SuccessEnvelope[KnowledgeBaseResource],
        tags=["Knowledge Bases"],
    )
    def update_knowledge_base(
        kb_id: str,
        payload: KnowledgeBaseUpdate,
        principal: Principal,
        database: Database,
    ) -> dict[str, Any]:
        return success(
            database.update_kb(principal["user_id"], kb_id, payload.model_dump(exclude_unset=True))
        )

    @app.delete(
        "/v1/knowledge-bases/{kb_id}",
        response_model=SuccessEnvelope[DeletionResult],
        tags=["Knowledge Bases"],
    )
    def delete_knowledge_base(
        kb_id: str, principal: Principal, database: Database
    ) -> dict[str, Any]:
        database.delete_kb(principal["user_id"], kb_id)
        return success({"id": kb_id, "deleted": True})

    @app.post(
        "/v1/knowledge-bases/{kb_id}/documents",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=SuccessEnvelope[DocumentResource],
        tags=["Documents"],
    )
    def create_document(
        kb_id: str,
        payload: DocumentCreate,
        request: Request,
        principal: Principal,
        database: Database,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        operation = f"documents.create:{kb_id}"
        cached = database.idempotent_get(principal["user_id"], idempotency_key, operation)
        if cached:
            return success(cached)
        resource = database.create_document(
            principal["user_id"], kb_id, payload.file_id, payload.title, payload.metadata
        )
        public = {
            key: value for key, value in resource.items() if key not in {"extraction_id", "user_id"}
        }
        database.idempotent_put(principal["user_id"], idempotency_key, operation, public)
        request.app.state.executor.submit(
            run_indexing, database, principal["user_id"], kb_id, resource["id"]
        )
        return success(public)

    @app.get(
        "/v1/knowledge-bases/{kb_id}/documents",
        response_model=SuccessEnvelope[ListData[DocumentResource]],
        tags=["Documents"],
    )
    def list_documents(
        kb_id: str,
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return success(database.list_documents(principal["user_id"], kb_id, limit, offset))

    @app.get(
        "/v1/knowledge-bases/{kb_id}/documents/{document_id}",
        response_model=SuccessEnvelope[DocumentResource],
        tags=["Documents"],
    )
    def get_document(
        kb_id: str, document_id: str, principal: Principal, database: Database
    ) -> dict[str, Any]:
        return success(database.document(principal["user_id"], kb_id, document_id))

    @app.delete(
        "/v1/knowledge-bases/{kb_id}/documents/{document_id}",
        response_model=SuccessEnvelope[DeletionResult],
        tags=["Documents"],
    )
    def delete_document(
        kb_id: str, document_id: str, principal: Principal, database: Database
    ) -> dict[str, Any]:
        database.delete_document(principal["user_id"], kb_id, document_id)
        return success({"id": document_id, "deleted": True})

    @app.post(
        "/v1/knowledge-bases/{kb_id}/search",
        response_model=SuccessEnvelope[SearchResults],
        tags=["Search"],
    )
    def semantic_search(
        kb_id: str, payload: SearchRequest, principal: Principal, database: Database
    ) -> dict[str, Any]:
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                payload.query,
                top_k=payload.top_k,
                threshold=payload.threshold,
                metadata_filter=payload.filter,
            )
        )

    @app.post(
        "/v1/knowledge-bases/{kb_id}/hybrid-search",
        response_model=SuccessEnvelope[SearchResults],
        tags=["Search"],
    )
    def hybrid_search(
        kb_id: str, payload: HybridSearchRequest, principal: Principal, database: Database
    ) -> dict[str, Any]:
        return success(
            search(
                database,
                principal["user_id"],
                kb_id,
                payload.query,
                top_k=payload.top_k,
                vector_weight=payload.vector_weight,
                keyword_weight=payload.keyword_weight,
            )
        )

    @app.post(
        "/v1/webhooks",
        status_code=status.HTTP_201_CREATED,
        response_model=SuccessEnvelope[WebhookResource],
        tags=["Webhooks"],
    )
    def create_webhook(
        payload: WebhookCreate,
        principal: Principal,
        database: Database,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "webhooks.create")
        if cached:
            return success(cached)
        resource = database.create_webhook(
            principal["user_id"], {**payload.model_dump(mode="json"), "url": str(payload.url)}
        )
        database.idempotent_put(principal["user_id"], idempotency_key, "webhooks.create", resource)
        return success(resource)

    @app.get(
        "/v1/webhooks",
        response_model=SuccessEnvelope[ListData[WebhookResource]],
        tags=["Webhooks"],
    )
    def list_webhooks(
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return success(database.list_webhooks(principal["user_id"], limit, offset))

    @app.get(
        "/v1/webhooks/{webhook_id}",
        response_model=SuccessEnvelope[WebhookResource],
        tags=["Webhooks"],
    )
    def get_webhook(webhook_id: str, principal: Principal, database: Database) -> dict[str, Any]:
        return success(database.webhook(principal["user_id"], webhook_id))

    @app.patch(
        "/v1/webhooks/{webhook_id}",
        response_model=SuccessEnvelope[WebhookResource],
        tags=["Webhooks"],
    )
    def update_webhook(
        webhook_id: str, payload: WebhookUpdate, principal: Principal, database: Database
    ) -> dict[str, Any]:
        changes = payload.model_dump(mode="json", exclude_unset=True)
        if payload.url is not None:
            changes["url"] = str(payload.url)
        return success(database.update_webhook(principal["user_id"], webhook_id, changes))

    @app.delete(
        "/v1/webhooks/{webhook_id}",
        response_model=SuccessEnvelope[DeletionResult],
        tags=["Webhooks"],
    )
    def delete_webhook(webhook_id: str, principal: Principal, database: Database) -> dict[str, Any]:
        database.delete_webhook(principal["user_id"], webhook_id)
        return success({"id": webhook_id, "deleted": True})

    @app.post(
        "/v1/api-keys",
        status_code=status.HTTP_201_CREATED,
        response_model=SuccessEnvelope[APIKeyResource],
        tags=["API Keys"],
    )
    def create_api_key(
        payload: APIKeyCreate,
        principal: Principal,
        database: Database,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        cached = database.idempotent_get(principal["user_id"], idempotency_key, "api-keys.create")
        if cached:
            return success(cached)
        resource = database.create_api_key(principal["user_id"], payload.model_dump(mode="json"))
        database.idempotent_put(principal["user_id"], idempotency_key, "api-keys.create", resource)
        return success(resource)

    @app.get(
        "/v1/api-keys",
        response_model=SuccessEnvelope[ListData[APIKeyResource]],
        tags=["API Keys"],
    )
    def list_api_keys(
        principal: Principal,
        database: Database,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return success(database.list_api_keys(principal["user_id"], limit, offset))

    @app.delete(
        "/v1/api-keys/{key_id}",
        response_model=SuccessEnvelope[DeletionResult],
        tags=["API Keys"],
    )
    def revoke_api_key(key_id: str, principal: Principal, database: Database) -> dict[str, Any]:
        database.revoke_api_key(principal["user_id"], key_id)
        return success({"id": key_id, "deleted": True})

    @app.get("/v1/usage/stats", response_model=SuccessEnvelope[dict[str, Any]], tags=["Usage"])
    def usage_stats(principal: Principal, database: Database) -> dict[str, Any]:
        return success(database.usage(principal["user_id"]))

    @app.get("/v1/usage/limits", response_model=SuccessEnvelope[dict[str, Any]], tags=["Usage"])
    def usage_limits(_: Principal) -> dict[str, Any]:
        return success(
            {
                "api_calls": {"limit": None, "window": "unlimited"},
                "storage": {"limit_bytes": current.storage_limit_bytes},
                "files": {"max_file_size_bytes": current.max_file_size_bytes},
            }
        )

    return app


app = create_app()
