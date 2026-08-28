"""Handwritten authentication adapter used by generated FastAPI bindings."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import BackgroundTasks, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from unifiles_server_protocol.models.extra_models import TokenModel

from .database import Store
from .errors import APIError

_request_context: ContextVar[Request] = ContextVar("unifiles_request")
_principal_context: ContextVar[dict[str, Any]] = ContextVar("unifiles_principal")
_background_context: ContextVar[BackgroundTasks] = ContextVar("unifiles_background_tasks")
bearer_auth = HTTPBearer(auto_error=False)


def authenticate_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Authenticate one generated route and bind its handwritten implementation context."""

    if not credentials or credentials.scheme.lower() != "bearer":
        raise APIError(401, "MISSING_API_KEY", "Authorization: Bearer <api-key> is required")

    database: Store = request.app.state.store
    principal = database.authenticate(credentials.credentials)
    parts = request.url.path.removeprefix("/v1/").split("/")
    domain = {"knowledge-bases": "kb", "api-keys": "api_keys"}.get(parts[0], parts[0])
    action = (
        "read" if request.method == "GET" or parts[-1] in {"search", "hybrid-search"} else "write"
    )
    scopes = set(principal["scopes"])
    if not ({"*", f"{domain}:*", f"{domain}:{action}"} & scopes):
        raise APIError(
            403,
            "INSUFFICIENT_SCOPE",
            f"API key requires {domain}:{action}",
            details={"required_scope": f"{domain}:{action}"},
        )

    _request_context.set(request)
    _principal_context.set(principal)
    _background_context.set(background_tasks)
    return principal


async def get_bearer_auth(
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> TokenModel:
    principal = authenticate_request(request, credentials, background_tasks)
    return TokenModel(sub=str(principal["user_id"]))


def current_context() -> tuple[Request, dict[str, Any], Store]:
    """Return request-scoped state for a handwritten protocol implementation."""

    request = _request_context.get()
    principal = _principal_context.get()
    return request, principal, request.app.state.store


def add_background_task(function: Any, *args: Any, **kwargs: Any) -> None:
    _background_context.get().add_task(function, *args, **kwargs)
