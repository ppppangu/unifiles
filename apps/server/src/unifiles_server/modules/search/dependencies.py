"""FastAPI dependency provider for search adapters."""

from unifiles_server_protocol.apis.search_api_base import BaseSearchApi

from .implementation import SearchImplementation


def get_search_api_implementation() -> BaseSearchApi:
    return SearchImplementation()
