"""FastAPI dependency provider for document adapters."""

from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi

from .implementation import DocumentsImplementation


def get_documents_api_implementation() -> BaseDocumentsApi:
    return DocumentsImplementation()
