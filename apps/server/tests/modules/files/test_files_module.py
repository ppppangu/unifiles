from __future__ import annotations

import pytest
from unifiles_server.modules.files.adapter import (
    FilesAdapter,
    parse_object,
    parse_tags,
    sanitize_filename,
)
from unifiles_server.modules.files.providers import (
    get_files_service,
    provide_files_adapter,
)


def test_file_adapter_helpers_preserve_validation_behavior() -> None:
    assert parse_object('{"kind":"contract"}', "metadata") == {"kind": "contract"}
    assert parse_tags('["legal","legal"]') == ["legal"]
    assert parse_tags("legal, finance") == ["legal", "finance"]
    assert sanitize_filename("../合同?.txt") == "合同_.txt"


def test_files_provider_injects_transport_independent_service() -> None:
    adapter = provide_files_adapter(get_files_service())
    assert isinstance(adapter, FilesAdapter)


@pytest.mark.asyncio
async def test_supported_file_types_are_mapped_to_protocol_dto() -> None:
    adapter = FilesAdapter(get_files_service())
    response = await adapter.list_supported_file_types()

    assert response.data.document_types[0] == ".pdf"
    assert ".webp" in response.data.image_types
    assert response.data.all_types == response.data.document_types + response.data.image_types
