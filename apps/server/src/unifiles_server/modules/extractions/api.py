"""Static composition of generated extraction routes."""

from unifiles_server_protocol.apis.extractions_api import create_router

from ...shared.auth import get_bearer_auth
from .dependencies import get_extractions_api_implementation

router = create_router(
    get_implementation=get_extractions_api_implementation,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
