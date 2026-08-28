"""Compatibility exports for shared settings during C+ migration."""

from .shared.settings import Settings as Settings
from .shared.settings import settings as settings

__all__ = ["Settings", "settings"]
