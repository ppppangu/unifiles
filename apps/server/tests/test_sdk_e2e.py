from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from unifiles import AsyncUnifilesClient, UnifilesClient
from unifiles_server.app import create_app
from unifiles_server.settings import Settings


def app_for(tmp_path: Path):
    return create_app(Settings(data_dir=tmp_path, bootstrap_api_key="sk_e2e"))


def test_sync_python_sdk_against_real_server(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    with TestClient(app) as http:
        client = UnifilesClient(
            "sk_e2e", base_url="http://testserver", max_retries=0, _http_client=http
        )
        file = client.files.upload(
            content=b"Alpha project deadline is Friday.", filename="alpha.txt"
        )
        extraction = client.extractions.create(file.id).wait(poll_interval=0)
        kb = client.knowledge_bases.create("projects")
        document = client.knowledge_bases.documents.create(kb.id, file.id).wait(poll_interval=0)
        results = client.knowledge_bases.hybrid_search(
            kb.id, "project deadline", vector_weight=0.5, keyword_weight=0.5
        )

        assert extraction.markdown and "Friday" in extraction.markdown
        assert document.status == "indexed"
        assert results.chunks and "Friday" in results.chunks[0].content


@pytest.mark.asyncio
async def test_async_python_sdk_against_real_server(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    with TestClient(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as http:
            client = AsyncUnifilesClient(
                "sk_e2e", base_url="http://testserver", max_retries=0, _http_client=http
            )
            file = await client.files.upload(
                content=b"Beta release notes mention observability.", filename="beta.txt"
            )
            extraction = await client.extractions.create(file.id)
            await extraction.wait(poll_interval=0)
            kb = await client.knowledge_bases.create("releases")
            document = await client.knowledge_bases.documents.create(kb.id, file.id)
            await document.wait(poll_interval=0)
            results = await client.knowledge_bases.search(kb.id, "observability", top_k=3)

            assert extraction.status == "completed"
            assert document.status == "indexed"
            assert results.chunks
