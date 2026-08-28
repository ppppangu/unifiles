"""Validate the canonical OpenAPI source without requiring fresh generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from openapi_common import load_openapi, validate_openapi_invariants
from openapi_spec_validator import validate


def main() -> None:
    root = Path(__file__).parents[2]
    contract = root / "contracts" / "openapi" / "unifiles.yaml"
    document = load_openapi(contract)
    validate(document)
    operation_ids = validate_openapi_invariants(document)

    generator_version = (root / "codegen" / "VERSION").read_text(encoding="utf-8").strip()
    tool_configuration = json.loads((root / "openapitools.json").read_text(encoding="utf-8"))
    configured_version = tool_configuration["generator-cli"]["version"]
    if configured_version != generator_version:
        raise SystemExit(
            "generator version mismatch: "
            f"codegen/VERSION={generator_version}, openapitools.json={configured_version}"
        )

    print(
        "OpenAPI source is valid: "
        f"{len(document['paths'])} paths, {len(operation_ids)} operations, "
        f"generator {generator_version}"
    )


if __name__ == "__main__":
    main()
