"""Static composition of generated usage routes."""

from unifiles_server_protocol.apis.usage_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_usage_adapter

router = create_router(
    get_adapter=provide_usage_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
