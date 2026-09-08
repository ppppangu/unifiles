"""Static composition of generated file routes."""

from unifiles_server_protocol.apis.files_api import create_router

from ...shared.auth import get_bearer_auth
from .providers import provide_files_adapter

router = create_router(
    get_adapter=provide_files_adapter,
    get_token_BearerAuth=get_bearer_auth,
)

__all__ = ["router"]
