"""Validate the hand-maintained OpenAPI contract and its codegen invariants."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml
from openapi_spec_validator import validate

GENERATOR_VERSION = "7.24.0"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def main() -> None:
    root = Path(__file__).parents[1]
    contract = root / "api" / "openapi.yaml"
    document = yaml.safe_load(contract.read_text(encoding="utf-8"))
    validate(document)

    operation_ids: list[str] = []
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                raise SystemExit(f"{method.upper()} {path} is missing operationId")
            if not re.fullmatch(r"[a-z][A-Za-z0-9]*", operation_id):
                raise SystemExit(f"operationId must be lower camelCase: {operation_id}")
            operation_ids.append(operation_id)
            if path not in {"/health", "/v1/health"} and operation.get("security") != [
                {"BearerAuth": []}
            ]:
                raise SystemExit(f"{method.upper()} {path} must require BearerAuth")

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
        if version != GENERATOR_VERSION:
            raise SystemExit(
                f"{generated} uses OpenAPI Generator {version}; expected {GENERATOR_VERSION}"
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
        f"generator {GENERATOR_VERSION}"
    )


if __name__ == "__main__":
    main()
