"""Static composition of generated extraction routes."""

from unifiles_server_protocol.apis.extractions_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_extractions_adapter

router = create_router(
    get_adapter=provide_extractions_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
