"""Public exception hierarchy for the Unifiles Python SDK."""

from __future__ import annotations

from typing import Any


class UnifilesError(Exception):
    """Base error raised by the SDK."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "UNIFILES_ERROR",
        status_code: int | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details or {}

    def __str__(self) -> str:
        prefix = f"[{self.code}] " if self.code else ""
        suffix = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{prefix}{self.message}{suffix}"


class AuthenticationError(UnifilesError):
    """The API key is missing, invalid, or expired."""


class PermissionError(UnifilesError):
    """The API key cannot perform the requested operation."""


class NotFoundError(UnifilesError):
    """The requested resource does not exist."""


class ValidationError(UnifilesError):
    """The request is structurally invalid."""


class ConflictError(UnifilesError):
    """The request conflicts with the current resource state."""


class ProcessingError(UnifilesError):
    """An extraction or indexing task failed."""


class RateLimitError(UnifilesError):
    """The API rejected the request because of rate limiting."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(UnifilesError):
    """The API returned a server-side error."""


class TimeoutError(UnifilesError):
    """A request or long-running operation timed out."""


class TransportError(UnifilesError):
    """The API could not be reached or returned an invalid response."""


__all__ = [
    "AuthenticationError",
    "ConflictError",
    "NotFoundError",
    "PermissionError",
    "ProcessingError",
    "RateLimitError",
    "ServerError",
    "TimeoutError",
    "TransportError",
    "UnifilesError",
    "ValidationError",
]
