"""FastAPI dependency provider for knowledge-base adapters."""

from unifiles_server_protocol.apis.knowledge_bases_api_base import BaseKnowledgeBasesApi

from .implementation import KnowledgeBasesImplementation


def get_knowledge_bases_api_implementation() -> BaseKnowledgeBasesApi:
    return KnowledgeBasesImplementation()
