"""Compatibility exports for feature-owned services during C+ migration."""

from .modules.documents.service import run_indexing as run_indexing
from .modules.extractions.service import run_extraction as run_extraction
from .modules.search.service import embedding as embedding
from .modules.search.service import search as search
from .modules.webhooks.service import dispatch_event as dispatch_event

__all__ = ["dispatch_event", "embedding", "run_extraction", "run_indexing", "search"]
