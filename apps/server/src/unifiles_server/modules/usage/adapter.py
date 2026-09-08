"""OpenAPI transport adapter for usage and limit reporting."""

from __future__ import annotations

from typing import Any

from unifiles_server_protocol.apis.usage_api_base import BaseUsageApi

from ...shared.auth import current_context
from ...shared.responses import success


class UsageAdapter(BaseUsageApi):
    async def get_usage_stats(self) -> Any:
        _, principal, database = current_context()
        return success(database.usage(principal["user_id"]))

    async def get_usage_limits(self) -> Any:
        request, _, _ = current_context()
        settings = request.app.state.settings
        return success(
            {
                "api_calls": {"limit": None, "window": "unlimited"},
                "storage": {"limit_bytes": settings.storage_limit_bytes},
                "files": {"max_file_size_bytes": settings.max_file_size_bytes},
            }
        )
