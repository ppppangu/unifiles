"""Shared synchronous and asynchronous HTTP transports."""

from __future__ import annotations

import asyncio
import os
import random
import time
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TransportError,
    UnifilesError,
    ValidationError,
)
from .exceptions import (
    PermissionError as UnifilesPermissionError,
)
from .exceptions import (
    TimeoutError as UnifilesTimeoutError,
)

DEFAULT_BASE_URL = "https://api.unifiles.dev/v1"
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _normalize_base_url(value: str | None) -> str:
    base = (value or os.getenv("UNIFILES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _api_key(value: str | None) -> str:
    key = value or os.getenv("UNIFILES_API_KEY")
    if not key:
        raise ValidationError(
            "api_key is required; pass it explicitly or set UNIFILES_API_KEY",
            code="MISSING_API_KEY",
        )
    return key


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            return max(
                0.0,
                (
                    parsedate_to_datetime(raw) - parsedate_to_datetime(response.headers["date"])
                ).total_seconds(),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _backoff(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        explicit = _retry_after(response)
        if explicit is not None:
            return explicit
    cap = min(8.0, 0.5 * (2**attempt))
    return random.uniform(0, cap)  # noqa: S311 - retry jitter is not security-sensitive


def _error_from_response(response: httpx.Response) -> UnifilesError:
    request_id = response.headers.get("x-request-id")
    code = f"HTTP_{response.status_code}"
    message = response.reason_phrase or "Request failed"
    details: dict[str, Any] = {}
    retry_after = _retry_after(response)

    try:
        body = response.json()
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = str(error.get("code", code))
                message = str(error.get("message", message))
                details_value = error.get("details")
                details = details_value if isinstance(details_value, dict) else {}
                request_id = str(error.get("request_id") or request_id or "") or None
                raw_retry = error.get("retry_after")
                if isinstance(raw_retry, (int, float)):
                    retry_after = float(raw_retry)
            elif "detail" in body:
                message = str(body["detail"])
    except ValueError:
        if response.text:
            message = response.text[:500]

    kwargs: dict[str, Any] = {
        "code": code,
        "status_code": response.status_code,
        "request_id": request_id,
        "details": details,
    }
    if response.status_code == 401:
        return AuthenticationError(message, **kwargs)
    if response.status_code == 403:
        return UnifilesPermissionError(message, **kwargs)
    if response.status_code == 404:
        return NotFoundError(message, **kwargs)
    if response.status_code in {400, 413, 415, 422}:
        return ValidationError(message, **kwargs)
    if response.status_code == 409:
        return ConflictError(message, **kwargs)
    if response.status_code == 429:
        return RateLimitError(message, retry_after=retry_after, **kwargs)
    if response.status_code in {408, 504}:
        return UnifilesTimeoutError(message, **kwargs)
    if response.status_code >= 500:
        return ServerError(message, **kwargs)
    return UnifilesError(message, **kwargs)


def _unwrap(response: httpx.Response) -> Any:
    if response.is_error:
        raise _error_from_response(response)
    try:
        body = response.json()
    except ValueError as exc:
        raise TransportError(
            "The API returned invalid JSON",
            code="INVALID_RESPONSE",
            status_code=response.status_code,
            request_id=response.headers.get("x-request-id"),
        ) from exc
    if not isinstance(body, dict) or body.get("success") is not True or "data" not in body:
        raise TransportError(
            "The API returned an invalid success envelope",
            code="INVALID_RESPONSE",
            status_code=response.status_code,
            request_id=response.headers.get("x-request-id"),
        )
    return body["data"]


class SyncTransport:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.max_retries = max(0, max_retries)
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {
            "Authorization": f"Bearer {_api_key(api_key)}",
            "Accept": "application/json",
            "User-Agent": "unifiles-python/0.1.0",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = dict(self.headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        retry_allowed = method.upper() in {"GET", "HEAD", "OPTIONS", "DELETE"} or bool(
            idempotency_key
        )
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                )
            except httpx.TimeoutException as exc:
                if retry_allowed and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise UnifilesTimeoutError(str(exc), code="REQUEST_TIMEOUT") from exc
            except httpx.HTTPError as exc:
                if retry_allowed and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise TransportError(str(exc), code="TRANSPORT_ERROR") from exc
            if (
                retry_allowed
                and response.status_code in RETRYABLE_STATUS
                and attempt < self.max_retries
            ):
                time.sleep(_backoff(attempt, response))
                continue
            return _unwrap(response)
        raise AssertionError("unreachable")

    def request_binary(self, path: str) -> bytes:
        response = self.client.get(
            f"{self.base_url}/{path.lstrip('/')}",
            headers=self.headers,
        )
        if response.is_error:
            raise _error_from_response(response)
        return response.content

    def close(self) -> None:
        if self._owns_client:
            self.client.close()


class AsyncTransport:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.max_retries = max(0, max_retries)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.headers = {
            "Authorization": f"Bearer {_api_key(api_key)}",
            "Accept": "application/json",
            "User-Agent": "unifiles-python-async/0.1.0",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = dict(self.headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        retry_allowed = method.upper() in {"GET", "HEAD", "OPTIONS", "DELETE"} or bool(
            idempotency_key
        )
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                )
            except httpx.TimeoutException as exc:
                if retry_allowed and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise UnifilesTimeoutError(str(exc), code="REQUEST_TIMEOUT") from exc
            except httpx.HTTPError as exc:
                if retry_allowed and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise TransportError(str(exc), code="TRANSPORT_ERROR") from exc
            if (
                retry_allowed
                and response.status_code in RETRYABLE_STATUS
                and attempt < self.max_retries
            ):
                await asyncio.sleep(_backoff(attempt, response))
                continue
            return _unwrap(response)
        raise AssertionError("unreachable")

    async def request_binary(self, path: str) -> bytes:
        response = await self.client.get(
            f"{self.base_url}/{path.lstrip('/')}",
            headers=self.headers,
        )
        if response.is_error:
            raise _error_from_response(response)
        return response.content

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()


__all__ = ["AsyncTransport", "SyncTransport"]
