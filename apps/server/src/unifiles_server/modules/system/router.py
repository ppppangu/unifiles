"""Static composition of generated system routes."""

from unifiles_server_protocol.apis.system_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_system_adapter

router = create_router(
    get_adapter=provide_system_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
