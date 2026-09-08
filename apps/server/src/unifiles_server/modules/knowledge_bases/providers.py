"""FastAPI dependency provider for knowledge-base adapters."""

from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi

from .adapter import KnowledgeBasesAdapter


def provide_knowledge_bases_adapter() -> BaseKnowledgeBasesApi:
    return KnowledgeBasesAdapter()
