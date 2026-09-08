"""Export the deterministic operation-to-module ownership inventory used by the migration."""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from openapi_common import BUSINESS_TAGS, iter_operations, load_openapi


def render_inventory(contract: Path) -> str:
    document = load_openapi(contract)
    stream = io.StringIO(newline="")
    fieldnames = [
        "operation_id",
        "path",
        "method",
        "tag",
        "module",
        "base_api",
        "adapter",
        "provider",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for path, method, operation in iter_operations(document):
        tags = operation.get("tags")
        if not isinstance(tags, list) or len(tags) != 1 or tags[0] not in BUSINESS_TAGS:
            raise SystemExit(f"{method.upper()} {path} must have one known business tag")
        tag = str(tags[0])
        module, class_stem = BUSINESS_TAGS[tag]
        writer.writerow(
            {
                "operation_id": operation.get("operationId", ""),
                "path": path,
                "method": method.upper(),
                "tag": tag,
                "module": module,
                "base_api": f"Base{class_stem}Api",
                "adapter": f"{class_stem}Adapter",
                "provider": f"provide_{module}_adapter",
            }
        )
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()

    root = Path(__file__).parents[2]
    output = root / "migration" / "operation-ownership.csv"
    rendered = render_inventory(root / "contracts" / "openapi" / "unifiles.yaml")
    if options.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "operation ownership inventory is stale; "
                "run codegen/scripts/export_operation_ownership.py"
            )
        print("Operation ownership inventory is current")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output.relative_to(root)}")


if __name__ == "__main__":
    main()
