"""Validate the hand-maintained OpenAPI contract and its codegen invariants."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from openapi_common import BUSINESS_TAGS, iter_operations, load_openapi
from openapi_spec_validator import validate


def main() -> None:
    root = Path(__file__).parents[1]
    contract = root / "api" / "openapi.yaml"
    document = load_openapi(contract)
    validate(document)

    generator_version = (root / "codegen" / "VERSION").read_text(encoding="utf-8").strip()
    tool_configuration = json.loads((root / "openapitools.json").read_text(encoding="utf-8"))
    configured_version = tool_configuration["generator-cli"]["version"]
    if configured_version != generator_version:
        raise SystemExit(
            "generator version mismatch: "
            f"codegen/VERSION={generator_version}, openapitools.json={configured_version}"
        )

    operation_ids: list[str] = []
    for path, method, operation in iter_operations(document):
        operation_id = operation.get("operationId")
        if not operation_id:
            raise SystemExit(f"{method.upper()} {path} is missing operationId")
        if not re.fullmatch(r"[a-z][A-Za-z0-9]*", operation_id):
            raise SystemExit(f"operationId must be lower camelCase: {operation_id}")
        operation_ids.append(operation_id)

        tags = operation.get("tags")
        if not isinstance(tags, list) or len(tags) != 1:
            raise SystemExit(f"{method.upper()} {path} must have exactly one business tag")
        if tags[0] not in BUSINESS_TAGS:
            raise SystemExit(f"{method.upper()} {path} uses unknown business tag: {tags[0]}")

        expected_security: list[dict[str, list[str]]] = (
            [] if path in {"/health", "/v1/health"} else [{"BearerAuth": []}]
        )
        if operation.get("security") != expected_security:
            requirement = "public security: []" if not expected_security else "BearerAuth"
            raise SystemExit(f"{method.upper()} {path} must require {requirement}")

    duplicates = sorted({item for item in operation_ids if operation_ids.count(item) > 1})
    if duplicates:
        raise SystemExit(f"duplicate operationId values: {', '.join(duplicates)}")

    generated_roots = [
        root / "apps" / "server" / "generated",
        root / "packages" / "python" / "generated",
        root / "packages" / "typescript" / "generated",
    ]
    contract_digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    for generated in generated_roots:
        version_file = generated / ".openapi-generator" / "VERSION"
        if not version_file.exists():
            raise SystemExit(f"missing generated output: {generated}")
        version = version_file.read_text(encoding="utf-8").strip()
        if version != generator_version:
            raise SystemExit(
                f"{generated} uses OpenAPI Generator {version}; expected {generator_version}"
            )
        digest_file = generated / ".openapi-generator" / "CONTRACT_SHA256"
        if (
            not digest_file.exists()
            or digest_file.read_text(encoding="utf-8").strip() != contract_digest
        ):
            raise SystemExit(
                f"stale generated output: {generated}; run scripts/generate_contract.py"
            )

    embedded = json.loads(
        (
            root
            / "apps"
            / "server"
            / "generated"
            / "src"
            / "unifiles_server_protocol"
            / "openapi.json"
        ).read_text(encoding="utf-8")
    )
    if embedded != document:
        raise SystemExit("embedded server contract is stale; run scripts/generate_contract.py")

    print(
        "OpenAPI contract is valid: "
        f"{len(document['paths'])} paths, {len(operation_ids)} operations, "
        f"generator {generator_version}"
    )


if __name__ == "__main__":
    main()
