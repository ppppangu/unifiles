"""Static composition of generated search routes."""

from unifiles_server_protocol.apis.search_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_search_adapter

router = create_router(
    get_adapter=provide_search_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
