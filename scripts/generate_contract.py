"""Compatibility entry point for the manifest-driven code generator."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-only", action="store_true")
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--typescript-only", action="store_true")
    options = parser.parse_args()

    selected = [
        target
        for target, enabled in (
            ("server-protocol-python", options.server_only),
            ("sdk-python", options.python_only),
            ("sdk-typescript", options.typescript_only),
        )
        if enabled
    ]
    targets = selected or ["all"]
    root = Path(__file__).parents[1]
    for target in targets:
        subprocess.run(
            [
                sys.executable,
                str(root / "codegen" / "scripts" / "codegen.py"),
                "generate",
                target,
            ],
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    main()
