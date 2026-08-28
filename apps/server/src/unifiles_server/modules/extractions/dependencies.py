"""FastAPI dependency provider for extraction adapters."""

from unifiles_server_protocol.apis.extractions_api_base import BaseExtractionsApi

from .implementation import ExtractionsImplementation


def get_extractions_api_implementation() -> BaseExtractionsApi:
    return ExtractionsImplementation()
