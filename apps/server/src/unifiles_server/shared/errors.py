from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "")) or f"req_{uuid.uuid4().hex}"


def error_response(request: Request, error: APIError) -> JSONResponse:
    identifier = request_id(request)
    return JSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "request_id": identifier,
            },
        },
        headers={"X-Request-ID": identifier},
    )


def public_validation_details(error: RequestValidationError) -> dict[str, Any]:
    """Keep public field locations without echoing inputs or framework internals."""

    errors: list[dict[str, str]] = []
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        errors.append(
            {
                "field": location,
                "code": "required" if issue.get("type") == "missing" else "invalid",
            }
        )
    return {"errors": errors}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, error: APIError) -> JSONResponse:
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        return error_response(
            request,
            APIError(
                422,
                "VALIDATION_ERROR",
                "Request validation failed",
                details=public_validation_details(error),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return error_response(
            request,
            APIError(
                error.status_code,
                codes.get(error.status_code, f"HTTP_{error.status_code}"),
                str(error.detail),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        return error_response(
            request,
            APIError(500, "INTERNAL_ERROR", "Internal server error"),
        )
