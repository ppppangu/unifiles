"""FastAPI dependency provider for API-key adapters."""

from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi

from .adapter import APIKeysAdapter


def provide_api_keys_adapter() -> BaseAPIKeysApi:
    return APIKeysAdapter()
