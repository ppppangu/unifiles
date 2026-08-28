"""Compatibility exports for shared authentication during C+ migration."""

from .shared.auth import add_background_task as add_background_task
from .shared.auth import authenticate_request as authenticate_request
from .shared.auth import current_context as current_context

__all__ = ["add_background_task", "authenticate_request", "current_context"]
