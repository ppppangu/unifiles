"""
Storage module public interface.

Exposes helpers for retrieving the storage orchestrator and ensuring it is
initialized before use.
"""

from .storage import Storage, get_initialized_storage, get_storage

__all__ = ["Storage", "get_storage", "get_initialized_storage"]
