"""Static composition of generated search routes."""

from unifiles_server_protocol.apis.search_api import create_router

from ...shared.auth import get_bearer_auth
from .dependencies import get_search_api_implementation

router = create_router(
    get_implementation=get_search_api_implementation,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
