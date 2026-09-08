"""FastAPI composition root for generated protocol routers and handwritten services."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from importlib.resources import files

import unifiles_server_protocol
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .modules.api_keys.router import router as api_keys_router
from .modules.documents.router import router as documents_router
from .modules.documents.service import run_indexing
from .modules.extractions.router import router as extractions_router
from .modules.extractions.service import run_extraction
from .modules.files.router import router as files_router
from .modules.knowledge_bases.router import router as knowledge_bases_router
from .modules.search.router import router as search_router
from .modules.system.router import router as system_router
from .modules.usage.router import router as usage_router
from .modules.webhooks.router import router as webhooks_router
from .shared.database import Store
from .shared.errors import install_error_handlers
from .shared.settings import Settings
from .shared.settings import settings as default_settings


def install_canonical_schema(app: FastAPI) -> None:
    """Serve the exact contract that produced the generated route layer."""

    def canonical_openapi() -> dict:
        if app.openapi_schema is None:
            resource = files(unifiles_server_protocol).joinpath("openapi.json")
            app.openapi_schema = json.loads(resource.read_text(encoding="utf-8"))
        return app.openapi_schema

    app.openapi = canonical_openapi  # type: ignore[method-assign]


def create_app(config: Settings | None = None) -> FastAPI:
    current = config or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = Store(current)
        app.state.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="unifiles-task")
        for extraction in app.state.store.pending_extractions():
            app.state.executor.submit(
                run_extraction,
                app.state.store,
                extraction["user_id"],
                extraction["id"],
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
        description=(
            "Canonical contract for the self-hosted Unifiles document processing API. "
            "Server bindings and official SDK cores are generated from "
            "contracts/openapi/unifiles.yaml."
        ),
        lifespan=lifespan,
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
    app.include_router(api_keys_router)
    app.include_router(documents_router)
    app.include_router(extractions_router)
    app.include_router(files_router)
    app.include_router(knowledge_bases_router)
    app.include_router(search_router)
    app.include_router(system_router)
    app.include_router(usage_router)
    app.include_router(webhooks_router)
    install_canonical_schema(app)
    return app


app = create_app()
