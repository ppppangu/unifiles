"""Export the canonical OpenAPI contract from the versioned FastAPI routes."""

from __future__ import annotations

from pathlib import Path

import yaml
from unifiles_server.app import app


def main() -> None:
    destination = Path(__file__).parents[1] / "api" / "openapi.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(destination)


if __name__ == "__main__":
    main()
