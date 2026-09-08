"""Static composition of generated webhook routes."""

from unifiles_server_protocol.apis.webhooks_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_webhooks_adapter

router = create_router(
    get_adapter=provide_webhooks_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
