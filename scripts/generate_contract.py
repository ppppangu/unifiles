"""Regenerate private Python and TypeScript wire types from api/openapi.yaml."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def generate_python(root: Path) -> None:
    subprocess.run(
        [
            "datamodel-codegen",
            "--input",
            str(root / "api" / "openapi.yaml"),
            "--input-file-type",
            "openapi",
            "--output",
            str(root / "packages" / "python" / "src" / "unifiles" / "_generated" / "models.py"),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--target-python-version",
            "3.11",
            "--use-standard-collections",
            "--use-union-operator",
            "--disable-timestamp",
            "--formatters",
            "black",
            "isort",
        ],
        check=True,
        cwd=root,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--typescript-only", action="store_true")
    options = parser.parse_args()
    root = Path(__file__).parents[1]
    if not options.typescript_only:
        generate_python(root)
    if not options.python_only:
        subprocess.run(["npm", "run", "generate"], check=True, cwd=root)


if __name__ == "__main__":
    main()
