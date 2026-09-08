"""FastAPI dependency provider for usage adapters."""

from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi

from .adapter import UsageAdapter


def provide_usage_adapter() -> BaseUsageApi:
    return UsageAdapter()
