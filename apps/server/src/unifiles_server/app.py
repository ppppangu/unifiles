"""FastAPI composition root for generated protocol routers and handwritten services."""

from __future__ import annotations

import importlib
import json
import pkgutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from importlib.resources import files

import unifiles_server_protocol
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from unifiles_server_protocol import apis as protocol_apis

from .errors import install_error_handlers
from .services import run_extraction, run_indexing
from .settings import Settings
from .settings import settings as default_settings
from .store import Store


def include_protocol_routers(app: FastAPI) -> None:
    """Discover every generated tag router without maintaining a handwritten route list."""

    modules = sorted(
        item.name
        for item in pkgutil.iter_modules(protocol_apis.__path__)
        if item.name.endswith("_api") and not item.name.endswith("_api_base")
    )
    for name in modules:
        module = importlib.import_module(f"{protocol_apis.__name__}.{name}")
        app.include_router(module.router)


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
    include_protocol_routers(app)
    install_canonical_schema(app)
    return app


app = create_app()
