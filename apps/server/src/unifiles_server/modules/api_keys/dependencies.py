"""FastAPI dependency provider for API-key adapters."""

from unifiles_server_protocol.apis.api_keys_api_base import BaseAPIKeysApi

from .implementation import APIKeysImplementation


def get_api_keys_api_implementation() -> BaseAPIKeysApi:
    return APIKeysImplementation()
