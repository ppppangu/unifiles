"""Public synchronous and asynchronous Unifiles clients."""

from __future__ import annotations

import httpx

from ._transport import AsyncTransport, SyncTransport
from .resources import (
    APIKeysResource,
    AsyncAPIKeysResource,
    AsyncExtractionsResource,
    AsyncFilesResource,
    AsyncKnowledgeBasesResource,
    AsyncSystemResource,
    AsyncUsageResource,
    AsyncWebhooksResource,
    ExtractionsResource,
    FilesResource,
    KnowledgeBasesResource,
    SystemResource,
    UsageResource,
    WebhooksResource,
)


class UnifilesClient:
    """Synchronous entry point for every Unifiles API resource."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 3,
        _http_client: httpx.Client | None = None,
    ) -> None:
        self._transport = SyncTransport(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            client=_http_client,
        )
        self.raw = self._transport.apis
        self.files = FilesResource(self._transport)
        self.extractions = ExtractionsResource(self._transport)
        self.knowledge_bases = KnowledgeBasesResource(self._transport)
        self.webhooks = WebhooksResource(self._transport)
        self.api_keys = APIKeysResource(self._transport)
        self.usage = UsageResource(self._transport)
        self.system = SystemResource(self._transport)

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> UnifilesClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncUnifilesClient:
    """Asynchronous entry point for every Unifiles API resource."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30,
        max_retries: int = 3,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._transport = AsyncTransport(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            client=_http_client,
        )
        self.raw = self._transport.apis
        self.files = AsyncFilesResource(self._transport)
        self.extractions = AsyncExtractionsResource(self._transport)
        self.knowledge_bases = AsyncKnowledgeBasesResource(self._transport)
        self.webhooks = AsyncWebhooksResource(self._transport)
        self.api_keys = AsyncAPIKeysResource(self._transport)
        self.usage = AsyncUsageResource(self._transport)
        self.system = AsyncSystemResource(self._transport)

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    async def close(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncUnifilesClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


__all__ = ["AsyncUnifilesClient", "UnifilesClient"]
