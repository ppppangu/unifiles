"""FastAPI dependency provider for search adapters."""

from unifiles_server_protocol.apis.search_api_base import BaseSearchApi

from .adapter import SearchAdapter


def provide_search_adapter() -> BaseSearchApi:
    return SearchAdapter()
