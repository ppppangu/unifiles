"""Check that every contract operation is exposed by both public SDK facades."""

from __future__ import annotations

import re
from pathlib import Path

from openapi_common import iter_operations, load_openapi


def snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def main() -> None:
    root = Path(__file__).parents[2]
    contract = load_openapi(root / "contracts" / "openapi" / "unifiles.yaml")
    python_surface = (root / "packages/python/src/unifiles/resources.py").read_text(
        encoding="utf-8"
    )
    typescript_surface = (root / "packages/typescript/src/resources.ts").read_text(
        encoding="utf-8"
    )

    missing_python: list[str] = []
    missing_typescript: list[str] = []
    for _path, _method, operation in iter_operations(contract):
        operation_id = str(operation["operationId"])
        python_operation = snake_case(operation_id)
        if not re.search(rf"\.{re.escape(python_operation)}(?:_sync)?\b", python_surface):
            missing_python.append(operation_id)
        if not re.search(rf"\.{re.escape(operation_id)}\b", typescript_surface):
            missing_typescript.append(operation_id)

    if missing_python or missing_typescript:
        if missing_python:
            print(f"Python public facade is missing: {', '.join(missing_python)}")
        if missing_typescript:
            print(f"TypeScript public facade is missing: {', '.join(missing_typescript)}")
        raise SystemExit(1)

    print("Every contract operation is exposed by both public SDK facades")


if __name__ == "__main__":
    main()
