from __future__ import annotations

import pytest
from unifiles_server.modules.system.adapter import SystemAdapter
from unifiles_server.modules.system.providers import (
    get_system_service,
    provide_system_adapter,
)


@pytest.mark.asyncio
async def test_system_adapter_maps_service_results_to_protocol_dtos() -> None:
    adapter = provide_system_adapter(get_system_service())
    assert isinstance(adapter, SystemAdapter)

    health = await adapter.get_health()
    details = await adapter.get_health_details()

    assert health.data.status == "ok"
    assert health.data.version == "1.0.0"
    assert details.data.status == "ok"
    assert details.data.database == "ok"
    assert details.data.python_version
