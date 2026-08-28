"""FastAPI dependency provider for usage adapters."""

from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi

from .implementation import UsageImplementation


def get_usage_api_implementation() -> BaseUsageApi:
    return UsageImplementation()
