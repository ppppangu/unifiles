"""FastAPI dependency provider for webhook adapters."""

from unifiles_server_protocol.apis.webhooks_api_base import BaseWebhooksApi

from .implementation import WebhooksImplementation


def get_webhooks_api_implementation() -> BaseWebhooksApi:
    return WebhooksImplementation()
