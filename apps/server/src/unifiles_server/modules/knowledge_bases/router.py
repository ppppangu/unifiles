"""Static composition of generated knowledge-base routes."""

from unifiles_server_protocol.apis.knowledge_bases_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_knowledge_bases_adapter

router = create_router(
    get_adapter=provide_knowledge_bases_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
