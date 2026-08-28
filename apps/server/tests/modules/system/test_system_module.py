from __future__ import annotations

import pytest
from unifiles_server.modules.system.dependencies import (
    get_system_api_implementation,
    get_system_service,
)
from unifiles_server.modules.system.implementation import SystemImplementation


@pytest.mark.asyncio
async def test_system_adapter_maps_service_results_to_protocol_dtos() -> None:
    implementation = get_system_api_implementation(get_system_service())
    assert isinstance(implementation, SystemImplementation)

    health = await implementation.get_health()
    details = await implementation.get_health_details()

    assert health.data.status == "ok"
    assert health.data.version == "1.0.0"
    assert details.data.status == "ok"
    assert details.data.database == "ok"
    assert details.data.python_version
