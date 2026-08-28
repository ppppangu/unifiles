"""Compatibility exports for shared error handling during C+ migration."""

from .shared.errors import APIError as APIError
from .shared.errors import error_response as error_response
from .shared.errors import install_error_handlers as install_error_handlers
from .shared.errors import request_id as request_id

__all__ = ["APIError", "error_response", "install_error_handlers", "request_id"]
