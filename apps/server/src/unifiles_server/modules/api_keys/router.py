"""Static composition of generated API-key routes."""

from unifiles_server_protocol.apis.api_keys_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_api_keys_adapter

router = create_router(
    get_adapter=provide_api_keys_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
