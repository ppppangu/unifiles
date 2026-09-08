from __future__ import annotations

import mimetypes
from datetime import UTC, datetime

import httpx
import pytest
from unifiles import (
    AsyncUnifilesClient,
    NotFoundError,
    ProcessingError,
    ServerError,
    TransportError,
    UnifilesClient,
)
from unifiles import (
    ValidationError as SDKValidationError,
)

NOW = datetime.now(UTC).isoformat()


def envelope(data: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"success": True, "data": data})


def test_sync_resource_namespaces_and_file_mapping() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return envelope(
                {
                    "id": "file_1",
                    "filename": "hello.txt",
                    "content_type": "text/plain",
                    "size": 5,
                    "metadata": {"kind": "demo"},
                    "tags": ["test"],
                    "created_at": NOW,
                },
                201,
            )
        return envelope(
            {
                "items": [],
                "total": 0,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            }
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = UnifilesClient(
        "sk_test", base_url="http://example.test", max_retries=0, _http_client=http
    )
    assert type(client.raw.files).__module__.startswith("unifiles_generated.api.")
    uploaded = client.files.upload(
        content=b"hello",
        filename="hello.txt",
        metadata={"kind": "demo"},
        tags=["test"],
    )

    assert uploaded.id == "file_1"
    assert client.base_url == "http://example.test/v1"
    assert requests[0].headers["idempotency-key"]
    assert b'"kind": "demo"' in requests[0].content
    assert len(client.files.list()) == 0


def test_public_names_are_domain_specific_without_legacy_aliases() -> None:
    client = UnifilesClient("sk_test", base_url="http://example.test", max_retries=0)
    assert hasattr(client.system, "health")
    assert hasattr(client.system, "liveness")
    assert hasattr(client.system, "details")
    assert hasattr(client.files, "supported_types")
    assert hasattr(client.usage, "stats")
    assert hasattr(client.usage, "limits")
    assert hasattr(client.api_keys, "revoke")
    assert not hasattr(client.files, "list_supported_types")
    assert not hasattr(client.usage, "get_stats")
    assert not hasattr(client.usage, "get_limits")
    assert not hasattr(client.api_keys, "delete")
    client.close()


def test_error_envelope_maps_to_typed_exception() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "success": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": "missing",
                    "request_id": "req_1",
                },
            },
        )

    client = UnifilesClient(
        "sk_test",
        base_url="http://example.test",
        max_retries=0,
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(NotFoundError) as caught:
        client.files.get("missing")
    assert caught.value.code == "FILE_NOT_FOUND"
    assert caught.value.request_id == "req_1"


def test_sync_client_preserves_caller_owned_http_policy() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return envelope(
            {
                "id": "file_1",
                "filename": "hello.txt",
                "content_type": "text/plain",
                "size": 5,
                "metadata": {},
                "tags": [],
                "created_at": NOW,
            }
        )

    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"X-Client-Policy": "preserved"},
        cookies={"session": "caller-owned"},
    )
    client = UnifilesClient(
        "sk_test", base_url="http://example.test", max_retries=0, _http_client=http
    )

    assert client.files.get("file_1").id == "file_1"
    client.close()

    assert requests[0].headers["x-client-policy"] == "preserved"
    assert requests[0].headers["cookie"] == "session=caller-owned"
    assert http.is_closed is False
    http.close()


@pytest.mark.parametrize(
    "response_factory",
    [
        lambda: httpx.Response(200, text="not-json", headers={"content-type": "text/plain"}),
        lambda: httpx.Response(200, json={"unexpected": True}),
        lambda: httpx.Response(
            200,
            json={
                "data": {
                    "id": "file_1",
                    "filename": "hello.txt",
                    "content_type": "text/plain",
                    "size": 5,
                    "metadata": {},
                    "tags": [],
                    "created_at": NOW,
                }
            },
        ),
    ],
)
def test_invalid_success_responses_are_sanitized(response_factory) -> None:
    client = UnifilesClient(
        "sk_test",
        base_url="http://example.test",
        max_retries=0,
        _http_client=httpx.Client(transport=httpx.MockTransport(lambda _: response_factory())),
    )

    with pytest.raises(TransportError) as caught:
        client.files.get("file_1")

    assert caught.value.code == "INVALID_RESPONSE"
    assert caught.value.__cause__ is None
    client.close()


def test_request_model_validation_is_sanitized() -> None:
    requests: list[httpx.Request] = []
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(500)
        )
    )
    client = UnifilesClient(
        "sk_test", base_url="http://example.test", max_retries=0, _http_client=http
    )

    with pytest.raises(SDKValidationError) as caught:
        client.extractions.create("file_1", options={"extract_tables": "not-a-boolean"})

    assert caught.value.code == "INVALID_REQUEST"
    assert caught.value.__cause__ is None
    assert requests == []
    client.close()
    http.close()


@pytest.mark.parametrize("filename", ["payload", "payload.unifiles_sdk_mime_test"])
def test_upload_sends_explicit_mime_without_global_registration(filename: str) -> None:
    requests: list[httpx.Request] = []
    previous_mime = mimetypes.guess_type(filename)[0]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return envelope(
            {
                "id": "file_1",
                "filename": filename,
                "content_type": "application/vnd.unifiles.test",
                "size": 1,
                "metadata": {},
                "tags": [],
                "created_at": NOW,
            },
            201,
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = UnifilesClient(
        "sk_test", base_url="http://example.test", max_retries=0, _http_client=http
    )
    client.files.upload(
        content=b"x",
        filename=filename,
        content_type="application/vnd.unifiles.test",
    )
    client.close()

    assert b"application/vnd.unifiles.test" in requests[0].content
    assert mimetypes.guess_type(filename)[0] == previous_mime
    http.close()


def test_extraction_wait_updates_bound_object(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter(["pending", "processing", "completed"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            status = "pending"
        else:
            status = next(statuses)
        return envelope(
            {
                "id": "ext_1",
                "file_id": "file_1",
                "status": status,
                "mode": "normal",
                "progress": 100 if status == "completed" else 10,
                "markdown": "# Done" if status == "completed" else None,
                "created_at": NOW,
            },
            202 if request.method == "POST" else 200,
        )

    monkeypatch.setattr("unifiles.resources.time.sleep", lambda _: None)
    client = UnifilesClient(
        "sk_test",
        base_url="http://example.test",
        max_retries=0,
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    extraction = client.extractions.create("file_1")
    assert extraction.wait(timeout=1, poll_interval=0) is extraction
    assert extraction.markdown == "# Done"


@pytest.mark.asyncio
async def test_async_client_and_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter(["processing", "completed"])

    def handler(request: httpx.Request) -> httpx.Response:
        status = "pending" if request.method == "POST" else next(statuses)
        return envelope(
            {
                "id": "ext_async",
                "file_id": "file_1",
                "status": status,
                "mode": "normal",
                "markdown": "ok" if status == "completed" else None,
                "created_at": NOW,
            },
            202 if request.method == "POST" else 200,
        )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("unifiles.resources.asyncio.sleep", no_sleep)
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncUnifilesClient(
        "sk_test", base_url="http://example.test", max_retries=0, _http_client=http
    )
    extraction = await client.extractions.create("file_1")
    assert await extraction.wait(timeout=1, poll_interval=0) is extraction
    assert extraction.markdown == "ok"
    await http.aclose()


def test_retries_only_safe_or_idempotent_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"GET": 0, "PATCH": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts[request.method] += 1
        if request.method == "GET" and attempts["GET"] > 1:
            return envelope({"items": [], "total": 0, "limit": 50, "offset": 0, "has_more": False})
        return httpx.Response(
            503,
            json={"success": False, "error": {"code": "UNAVAILABLE", "message": "retry"}},
        )

    monkeypatch.setattr("unifiles._transport.time.sleep", lambda _: None)
    client = UnifilesClient(
        "sk_test",
        base_url="http://example.test",
        max_retries=2,
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert len(client.files.list()) == 0
    assert attempts["GET"] == 2

    with pytest.raises(ServerError):
        client.knowledge_bases.update("kb_1", name="new")
    assert attempts["PATCH"] == 1


def test_wait_raises_processing_error_for_terminal_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = "pending" if request.method == "POST" else "failed"
        return envelope(
            {
                "id": "ext_failed",
                "file_id": "file_1",
                "status": status,
                "mode": "normal",
                "error": (
                    {"code": "OCR_FAILED", "message": "OCR provider unavailable"}
                    if status == "failed"
                    else None
                ),
                "created_at": NOW,
            },
            202 if request.method == "POST" else 200,
        )

    client = UnifilesClient(
        "sk_test",
        base_url="http://example.test",
        max_retries=0,
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    extraction = client.extractions.create("file_1")
    with pytest.raises(ProcessingError) as caught:
        extraction.wait(poll_interval=0)
    assert caught.value.code == "OCR_FAILED"
