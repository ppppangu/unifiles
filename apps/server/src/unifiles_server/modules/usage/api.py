"""Static composition of generated usage routes."""

from unifiles_server_protocol.apis.usage_api import create_router

from ...shared.auth import get_bearer_auth
from .dependencies import get_usage_api_implementation

router = create_router(
    get_implementation=get_usage_api_implementation,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
