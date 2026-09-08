"""Static composition of generated document routes."""

from unifiles_server_protocol.apis.documents_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_documents_adapter

router = create_router(
    get_adapter=provide_documents_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
