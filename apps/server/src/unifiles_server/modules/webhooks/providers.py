"""FastAPI dependency provider for webhook adapters."""

from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi

from .adapter import WebhooksAdapter


def provide_webhooks_adapter() -> BaseWebhooksApi:
    return WebhooksAdapter()
