"""Fail when the checked-in OpenAPI document is stale or invalid."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from openapi_spec_validator import validate
from unifiles_server.app import app


def main() -> None:
    contract = Path(__file__).parents[1] / "api" / "openapi.yaml"
    actual = app.openapi()
    expected = yaml.safe_load(contract.read_text(encoding="utf-8"))
    validate(expected)
    if expected != actual:
        print(
            "api/openapi.yaml is stale; run uv run python scripts/export_openapi.py",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print("OpenAPI contract is valid and current")


if __name__ == "__main__":
    main()
