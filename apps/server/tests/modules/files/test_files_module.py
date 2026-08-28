from __future__ import annotations

import pytest
from unifiles_server.implementation.providers import (
    get_files_api_implementation as compatibility_provider,
)
from unifiles_server.modules.files.dependencies import (
    get_files_api_implementation,
    get_files_service,
)
from unifiles_server.modules.files.implementation import (
    FilesImplementation,
    parse_object,
    parse_tags,
    sanitize_filename,
)


def test_compatibility_provider_is_static_reexport() -> None:
    assert compatibility_provider is get_files_api_implementation


def test_file_adapter_helpers_preserve_validation_behavior() -> None:
    assert parse_object('{"kind":"contract"}', "metadata") == {"kind": "contract"}
    assert parse_tags('["legal","legal"]') == ["legal"]
    assert parse_tags("legal, finance") == ["legal", "finance"]
    assert sanitize_filename("../合同?.txt") == "合同_.txt"


def test_files_provider_injects_transport_independent_service() -> None:
    implementation = get_files_api_implementation(get_files_service())
    assert isinstance(implementation, FilesImplementation)


@pytest.mark.asyncio
async def test_supported_file_types_are_mapped_to_protocol_dto() -> None:
    implementation = FilesImplementation(get_files_service())
    response = await implementation.list_supported_file_types()

    assert response.data.document_types[0] == ".pdf"
    assert ".webp" in response.data.image_types
    assert response.data.all_types == response.data.document_types + response.data.image_types
