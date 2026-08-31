from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from unifiles_server.app import create_app
from unifiles_server.shared.database import Store, identifier
from unifiles_server.shared.errors import APIError
from unifiles_server.shared.settings import Settings


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        Settings(
            data_dir=tmp_path,
            bootstrap_api_key="sk_test_suite",
            cors_origins="http://localhost",
        )
    )
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = "Bearer sk_test_suite"
        yield test_client


def data(response):
    assert response.json()["success"] is True, response.text
    return response.json()["data"]


def wait_for_status(
    client: TestClient,
    url: str,
    expected: str,
    *,
    timeout: float = 5,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        resource = data(client.get(url))
        if resource["status"] == expected:
            return resource
        if resource["status"] in {"failed", "cancelled"}:
            pytest.fail(
                f"Task reached terminal status {resource['status']}: {resource.get('error')}"
            )
        if time.monotonic() >= deadline:
            pytest.fail(f"Timed out waiting for {expected}; latest status was {resource['status']}")
        time.sleep(0.01)


def test_generated_protocol_router_is_mounted(client: TestClient) -> None:
    route = next(route for route in client.app.routes if route.path == "/v1/files")
    assert route.endpoint.__module__.startswith("unifiles_server_protocol.apis.")


def test_complete_document_flow(client: TestClient) -> None:
    upload = client.post(
        "/v1/files",
        files={
            "file": (
                "contract.txt",
                b"Payment is due in thirty days. Late fees apply.",
                "text/plain",
            )
        },
        data={"metadata": '{"department":"legal"}', "tags": '["contract"]'},
        headers={"Idempotency-Key": "upload-1"},
    )
    assert upload.status_code == 201
    file = data(upload)
    assert file["filename"] == "contract.txt"

    repeated = client.post(
        "/v1/files",
        files={"file": ("ignored.txt", b"different", "text/plain")},
        data={"metadata": "{}", "tags": "[]"},
        headers={"Idempotency-Key": "upload-1"},
    )
    assert data(repeated)["id"] == file["id"]

    downloaded = client.get(f"/v1/files/{file['id']}/download")
    assert downloaded.content.startswith(b"Payment")

    extraction = data(
        client.post(
            "/v1/extractions",
            json={"file_id": file["id"], "mode": "normal", "options": {}},
        )
    )
    extraction = wait_for_status(client, f"/v1/extractions/{extraction['id']}", "completed")
    assert "Payment" in extraction["markdown"]

    kb = data(
        client.post(
            "/v1/knowledge-bases",
            json={
                "name": "legal",
                "description": "Legal documents",
                "chunking_strategy": {"type": "semantic", "chunk_size": 128, "overlap": 10},
                "metadata": {},
            },
        )
    )
    document = data(
        client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents",
            json={"file_id": file["id"], "title": "Contract", "metadata": {"year": 2026}},
        )
    )
    document = wait_for_status(
        client,
        f"/v1/knowledge-bases/{kb['id']}/documents/{document['id']}",
        "indexed",
    )
    assert document["chunk_count"] >= 1

    results = data(
        client.post(
            f"/v1/knowledge-bases/{kb['id']}/hybrid-search",
            json={"query": "payment due", "top_k": 3, "vector_weight": 0.5, "keyword_weight": 0.5},
        )
    )
    assert results["chunks"]
    assert "Payment" in results["chunks"][0]["content"]

    usage = data(client.get("/v1/usage/stats"))
    assert usage["storage"]["used_bytes"] == file["size"]
    assert usage["knowledge_bases"]["used"] == 1


def test_auxiliary_resources_and_error_envelope(client: TestClient) -> None:
    webhook = data(
        client.post(
            "/v1/webhooks",
            json={"url": "https://example.com/hook", "events": ["file.uploaded"]},
        )
    )
    updated = data(client.patch(f"/v1/webhooks/{webhook['id']}", json={"enabled": False}))
    assert updated["enabled"] is False
    assert data(client.delete(f"/v1/webhooks/{webhook['id']}"))["deleted"] is True

    created_key = data(
        client.post("/v1/api-keys", json={"name": "ci", "scopes": ["*"], "expires_at": None})
    )
    assert created_key["key"].startswith("sk_live_")
    assert any(
        item["id"] == created_key["id"] for item in data(client.get("/v1/api-keys"))["items"]
    )

    missing = client.get("/v1/files/missing")
    assert missing.status_code == 404
    body = missing.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FILE_NOT_FOUND"
    assert body["error"]["request_id"].startswith("req_")


def test_webhook_delivery_is_signed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    deliveries: list[dict] = []

    def deliver(url: str, **kwargs):
        deliveries.append({"url": url, **kwargs})
        return httpx.Response(200)

    monkeypatch.setattr("unifiles_server.modules.webhooks.service.httpx.post", deliver)
    webhook = data(
        client.post(
            "/v1/webhooks",
            json={"url": "https://example.com/hook", "events": ["file.uploaded"]},
        )
    )
    data(
        client.post(
            "/v1/files",
            files={"file": ("event.txt", b"event", "text/plain")},
            data={"metadata": "{}", "tags": "[]"},
        )
    )
    assert deliveries and deliveries[0]["url"] == "https://example.com/hook"
    headers = deliveries[0]["headers"]
    assert headers["X-Unifiles-Event"] == "file.uploaded"
    assert headers["X-Unifiles-Signature"].startswith("sha256=")
    assert data(client.get(f"/v1/webhooks/{webhook['id']}"))["last_delivery_at"]


def test_chinese_search_and_metadata_filter(client: TestClient) -> None:
    file = data(
        client.post(
            "/v1/files",
            files={
                "file": (
                    "合同.txt",
                    "合同中的违约责任包括支付违约金。".encode(),
                    "text/plain",
                )
            },
            data={"metadata": "{}", "tags": "[]"},
        )
    )
    extraction = data(
        client.post(
            "/v1/extractions",
            json={"file_id": file["id"], "mode": "normal", "options": {}},
        )
    )
    extraction = wait_for_status(client, f"/v1/extractions/{extraction['id']}", "completed")
    kb = data(client.post("/v1/knowledge-bases", json={"name": "合同", "metadata": {}}))
    document = data(
        client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents",
            json={
                "file_id": file["id"],
                "metadata": {"category": "contract"},
            },
        )
    )
    document = wait_for_status(
        client,
        f"/v1/knowledge-bases/{kb['id']}/documents/{document['id']}",
        "indexed",
    )
    results = data(
        client.post(
            f"/v1/knowledge-bases/{kb['id']}/search",
            json={
                "query": "违约责任",
                "top_k": 5,
                "threshold": 0,
                "filter": {"metadata.category": "contract"},
            },
        )
    )
    assert results["chunks"]
    assert "违约金" in results["chunks"][0]["content"]


def test_authentication_is_required(client: TestClient) -> None:
    response = client.get("/v1/files", headers={"Authorization": ""})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_API_KEY"


def test_scopes_and_unknown_routes_use_error_envelope(client: TestClient) -> None:
    key = data(
        client.post(
            "/v1/api-keys",
            json={"name": "reader", "scopes": ["files:read"], "expires_at": None},
        )
    )["key"]
    denied = client.post(
        "/v1/files",
        files={"file": ("blocked.txt", b"blocked", "text/plain")},
        data={"metadata": "{}", "tags": "[]"},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "INSUFFICIENT_SCOPE"

    missing = client.get("/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    invalid_scope = client.post(
        "/v1/api-keys",
        json={"name": "invalid", "scopes": ["private-invalid-scope"], "expires_at": None},
    )
    assert invalid_scope.status_code == 422
    invalid_error = invalid_scope.json()["error"]
    assert invalid_error["code"] == "VALIDATION_ERROR"
    assert invalid_error["details"] == {
        "errors": [{"field": "body.scopes", "code": "invalid"}]
    }
    assert "private-invalid-scope" not in invalid_scope.text

    invalid_strategy = client.post(
        "/v1/knowledge-bases",
        json={"name": "invalid", "chunking_strategy": {"type": "unknown"}},
    )
    assert invalid_strategy.status_code == 422


def test_startup_recovers_persisted_processing_tasks(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, bootstrap_api_key="sk_recovery")
    store = Store(settings)
    file_id = identifier("file")
    directory = settings.files_dir / "local" / file_id
    directory.mkdir(parents=True)
    path = directory / "recovery.txt"
    path.write_text("Recovered tasks remain durable.", encoding="utf-8")
    store.insert_file(
        file_id=file_id,
        user_id="local",
        filename=path.name,
        content_type="text/plain",
        size=path.stat().st_size,
        metadata={},
        tags=[],
        storage_path=str(path),
    )
    extraction = store.create_extraction("local", file_id, "normal", {})
    store.close()

    app = create_app(settings)
    with TestClient(app) as recovered:
        recovered.headers["Authorization"] = "Bearer sk_recovery"
        result = wait_for_status(recovered, f"/v1/extractions/{extraction['id']}", "completed")
        assert "durable" in result["markdown"]


def test_bootstrap_key_rotates_on_restart(tmp_path: Path) -> None:
    first = Store(Settings(data_dir=tmp_path, bootstrap_api_key="sk_first"))
    assert first.authenticate("sk_first")["user_id"] == "local"
    first.close()

    second = Store(Settings(data_dir=tmp_path, bootstrap_api_key="sk_second"))
    with pytest.raises(APIError) as old_key:
        second.authenticate("sk_first")
    assert getattr(old_key.value, "code", None) == "INVALID_API_KEY"
    assert second.authenticate("sk_second")["user_id"] == "local"
    second.close()


def test_remote_ocr_provider_handles_advanced_and_image_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    def remote_ocr(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "markdown": "# 扫描合同\n\n违约责任",
                    "total_pages": 1,
                    "metadata": {"provider": "test"},
                },
            },
        )

    monkeypatch.setattr("unifiles_server.modules.extractions.service.httpx.post", remote_ocr)
    app = create_app(
        Settings(
            data_dir=tmp_path,
            bootstrap_api_key="sk_ocr",
            ocr_endpoint="https://ocr.example.test/extract",
            ocr_api_key="ocr-secret",
        )
    )
    with TestClient(app) as ocr_client:
        ocr_client.headers["Authorization"] = "Bearer sk_ocr"
        file = data(
            ocr_client.post(
                "/v1/files",
                files={"file": ("scan.png", b"not-a-real-image", "image/png")},
                data={"metadata": "{}", "tags": "[]"},
            )
        )
        extraction = data(
            ocr_client.post(
                "/v1/extractions",
                json={
                    "file_id": file["id"],
                    "mode": "advanced",
                    "options": {"ocr_provider": "remote"},
                },
            )
        )
        extraction = wait_for_status(ocr_client, f"/v1/extractions/{extraction['id']}", "completed")
        assert extraction["markdown"].startswith("# 扫描合同")
        assert extraction["metadata"]["parser"] == "remote-ocr"
        assert calls[0]["headers"]["Authorization"] == "Bearer ocr-secret"
