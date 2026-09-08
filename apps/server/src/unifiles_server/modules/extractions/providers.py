"""FastAPI dependency provider for extraction adapters."""

from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi

from .adapter import ExtractionsAdapter


def provide_extractions_adapter() -> BaseExtractionsApi:
    return ExtractionsAdapter()
