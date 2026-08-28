"""Temporary static provider exports used by generated routers during migration."""

from ..modules.api_keys.dependencies import (
    get_api_keys_api_implementation as get_api_keys_api_implementation,
)
from ..modules.documents.dependencies import (
    get_documents_api_implementation as get_documents_api_implementation,
)
from ..modules.extractions.dependencies import (
    get_extractions_api_implementation as get_extractions_api_implementation,
)
from ..modules.files.dependencies import (
    get_files_api_implementation as get_files_api_implementation,
)
from ..modules.knowledge_bases.dependencies import (
    get_knowledge_bases_api_implementation as get_knowledge_bases_api_implementation,
)
from ..modules.search.dependencies import (
    get_search_api_implementation as get_search_api_implementation,
)
from ..modules.system.dependencies import (
    get_system_api_implementation as get_system_api_implementation,
)
from ..modules.usage.dependencies import (
    get_usage_api_implementation as get_usage_api_implementation,
)
from ..modules.webhooks.dependencies import (
    get_webhooks_api_implementation as get_webhooks_api_implementation,
)

__all__ = [
    "get_api_keys_api_implementation",
    "get_documents_api_implementation",
    "get_extractions_api_implementation",
    "get_files_api_implementation",
    "get_knowledge_bases_api_implementation",
    "get_search_api_implementation",
    "get_system_api_implementation",
    "get_usage_api_implementation",
    "get_webhooks_api_implementation",
]
