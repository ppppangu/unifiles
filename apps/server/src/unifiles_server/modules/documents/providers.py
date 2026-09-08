"""FastAPI dependency provider for document adapters."""

from unifiles_server_protocol.apis.documents_api_base import BaseDocumentsApi

from .adapter import DocumentsAdapter


def provide_documents_adapter() -> BaseDocumentsApi:
    return DocumentsAdapter()
