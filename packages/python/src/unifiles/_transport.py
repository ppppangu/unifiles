"""Transport policy around the generated Python SDK core."""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import ValidationError as PydanticValidationError
from unifiles_generated.api.api_keys_api import APIKeysApi
from unifiles_generated.api.documents_api import DocumentsApi
from unifiles_generated.api.extractions_api import ExtractionsApi
from unifiles_generated.api.files_api import FilesApi
from unifiles_generated.api.knowledge_bases_api import KnowledgeBasesApi
from unifiles_generated.api.search_api import SearchApi
from unifiles_generated.api.system_api import SystemApi
from unifiles_generated.api.usage_api import UsageApi
from unifiles_generated.api.webhooks_api import WebhooksApi
from unifiles_generated.api_client import ApiClient
from unifiles_generated.configuration import Configuration
from unifiles_generated.exceptions import ApiException
from unifiles_generated.sync_helper import run_sync

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
from .exceptions import PermissionError as UnifilesPermissionError
from .exceptions import TimeoutError as UnifilesTimeoutError

DEFAULT_BASE_URL = "https://api.unifiles.dev/v1"
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _normalize_base_url(value: str | None) -> str:
    base = (value or os.getenv("UNIFILES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _api_origin(base_url: str) -> str:
    return base_url.removesuffix("/v1")


def _api_key(value: str | None) -> str:
    key = value or os.getenv("UNIFILES_API_KEY")
    if not key:
        raise ValidationError(
            "api_key is required; pass it explicitly or set UNIFILES_API_KEY",
            code="MISSING_API_KEY",
        )
    return key


def _retry_after(headers: Any) -> float | None:
    raw = headers.get("retry-after") if headers else None
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        try:
            return max(
                0.0,
                (
                    parsedate_to_datetime(str(raw)) - parsedate_to_datetime(str(headers["date"]))
                ).total_seconds(),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _backoff(attempt: int, headers: Any = None) -> float:
    explicit = _retry_after(headers)
    if explicit is not None:
        return explicit
    return random.uniform(0, min(8.0, 0.5 * (2**attempt)))  # noqa: S311


def _error_fields(error: ApiException) -> tuple[str, str, dict[str, Any], str | None]:
    status = int(error.status or 0)
    code = f"HTTP_{status}"
    message = str(error.reason or "Request failed")
    details: dict[str, Any] = {}
    request_id = error.headers.get("x-request-id") if error.headers else None

    detail = getattr(error.data, "error", None)
    if detail is not None:
        code = str(getattr(detail, "code", code))
        message = str(getattr(detail, "message", message))
        details = getattr(detail, "details", None) or {}
        request_id = getattr(detail, "request_id", None) or request_id
        return code, message, details, request_id

    try:
        body = json.loads(error.body or "")
    except (TypeError, ValueError):
        body = None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        wire = body["error"]
        code = str(wire.get("code", code))
        message = str(wire.get("message", message))
        details = wire.get("details") if isinstance(wire.get("details"), dict) else {}
        request_id = str(wire.get("request_id") or request_id or "") or None
    return code, message, details, request_id


def _public_error(error: ApiException) -> UnifilesError:
    status = int(error.status or 0)
    code, message, details, request_id = _error_fields(error)
    if status <= 0:
        return TransportError(
            "The API returned an invalid response",
            code="INVALID_RESPONSE",
            request_id=request_id,
        )
    kwargs: dict[str, Any] = {
        "code": code,
        "status_code": status or None,
        "request_id": request_id,
        "details": details,
    }
    if status == 401:
        return AuthenticationError(message, **kwargs)
    if status == 403:
        return UnifilesPermissionError(message, **kwargs)
    if status == 404:
        return NotFoundError(message, **kwargs)
    if status in {400, 413, 415, 422}:
        return ValidationError(message, **kwargs)
    if status == 409:
        return ConflictError(message, **kwargs)
    if status == 429:
        return RateLimitError(message, retry_after=_retry_after(error.headers), **kwargs)
    if status in {408, 504}:
        return UnifilesTimeoutError(message, **kwargs)
    if status >= 500:
        return ServerError(message, **kwargs)
    return UnifilesError(message, **kwargs)


def _validate_success_envelope(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return value
    fields_set: set[str] = getattr(value, "model_fields_set", set())
    if (
        "success" not in fields_set
        or getattr(value, "success", None) is not True
        or not hasattr(value, "data")
    ):
        raise TransportError(
            "The API returned an invalid success envelope",
            code="INVALID_RESPONSE",
        )
    return value


class _SyncClientTransport(httpx.AsyncBaseTransport):
    """Run a caller-owned synchronous client without discarding its policy."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        content = await request.aread()

        def send() -> tuple[int, list[tuple[str, str]], bytes, dict[str, Any]]:
            sync_request = self._client.build_request(
                request.method,
                request.url,
                content=content,
                headers=request.headers,
                extensions=request.extensions,
            )
            response = self._client.send(sync_request)
            try:
                body = response.read()
                extensions = {
                    key: value
                    for key, value in response.extensions.items()
                    if key in {"http_version", "reason_phrase"}
                }
                return response.status_code, response.headers.multi_items(), body, extensions
            finally:
                response.close()

        status, headers, body, extensions = await asyncio.to_thread(send)
        return httpx.Response(
            status,
            headers=headers,
            content=body,
            extensions=extensions,
            request=request,
        )


def _as_async_client(
    client: httpx.Client | httpx.AsyncClient | None,
    *,
    timeout: float,
) -> tuple[httpx.AsyncClient, bool]:
    if isinstance(client, httpx.AsyncClient):
        return client, False
    if client is None:
        return httpx.AsyncClient(timeout=timeout), True
    return httpx.AsyncClient(transport=_SyncClientTransport(client), timeout=timeout), True


@dataclass(frozen=True)
class GeneratedAPIs:
    """Direct access to every endpoint generated from the OpenAPI contract."""

    files: FilesApi
    extractions: ExtractionsApi
    knowledge_bases: KnowledgeBasesApi
    documents: DocumentsApi
    search: SearchApi
    webhooks: WebhooksApi
    api_keys: APIKeysApi
    usage: UsageApi
    system: SystemApi


class ProtocolTransport:
    """Configure generated APIs and apply handwritten retry/error policy once."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 3,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        configuration = Configuration(
            host=_api_origin(self.base_url), access_token=_api_key(api_key)
        )
        self.api_client = ApiClient(configuration)
        self.http, self._owns_http = _as_async_client(client, timeout=timeout)
        self.api_client.rest_client.pool_manager = self.http
        self.api_client.user_agent = "unifiles-python/0.1.0"
        self.apis = GeneratedAPIs(
            files=FilesApi(self.api_client),
            extractions=ExtractionsApi(self.api_client),
            knowledge_bases=KnowledgeBasesApi(self.api_client),
            documents=DocumentsApi(self.api_client),
            search=SearchApi(self.api_client),
            webhooks=WebhooksApi(self.api_client),
            api_keys=APIKeysApi(self.api_client),
            usage=UsageApi(self.api_client),
            system=SystemApi(self.api_client),
        )

    def call_sync(
        self,
        method: Callable[..., Any],
        *,
        retry_allowed: bool = False,
        **kwargs: Any,
    ) -> Any:
        kwargs.setdefault("_request_timeout", self.timeout)
        for attempt in range(self.max_retries + 1):
            try:
                return _validate_success_envelope(method(**kwargs))
            except ApiException as error:
                status = int(error.status or 0)
                if retry_allowed and status in RETRYABLE_STATUS and attempt < self.max_retries:
                    time.sleep(_backoff(attempt, error.headers))
                    continue
                public_error = _public_error(error)
                if status <= 0:
                    raise public_error from None
                raise public_error from error
            except PydanticValidationError:
                raise ValidationError(
                    "Request validation failed",
                    code="INVALID_REQUEST",
                ) from None
            except httpx.TimeoutException as error:
                if retry_allowed and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise UnifilesTimeoutError(str(error), code="REQUEST_TIMEOUT") from error
            except httpx.HTTPError as error:
                if retry_allowed and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise TransportError(str(error), code="TRANSPORT_ERROR") from error
        raise AssertionError("unreachable")

    async def call_async(
        self,
        method: Callable[..., Any],
        *,
        retry_allowed: bool = False,
        **kwargs: Any,
    ) -> Any:
        kwargs.setdefault("_request_timeout", self.timeout)
        for attempt in range(self.max_retries + 1):
            try:
                return _validate_success_envelope(await method(**kwargs))
            except ApiException as error:
                status = int(error.status or 0)
                if retry_allowed and status in RETRYABLE_STATUS and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt, error.headers))
                    continue
                public_error = _public_error(error)
                if status <= 0:
                    raise public_error from None
                raise public_error from error
            except PydanticValidationError:
                raise ValidationError(
                    "Request validation failed",
                    code="INVALID_REQUEST",
                ) from None
            except httpx.TimeoutException as error:
                if retry_allowed and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise UnifilesTimeoutError(str(error), code="REQUEST_TIMEOUT") from error
            except httpx.HTTPError as error:
                if retry_allowed and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise TransportError(str(error), code="TRANSPORT_ERROR") from error
        raise AssertionError("unreachable")

    def close(self) -> None:
        if self._owns_http:
            run_sync(self.http.aclose())

    async def aclose(self) -> None:
        if self._owns_http:
            await self.http.aclose()


class SyncTransport(ProtocolTransport):
    pass


class AsyncTransport(ProtocolTransport):
    pass
