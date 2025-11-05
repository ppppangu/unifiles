#!/usr/bin/env python3
"""
Project cleanup utility.

Removes common caches, build outputs, and temporary artifacts to keep the
workspace tidy. Defaults to a dry-run that only prints what would be removed.

Usage examples:
  - Dry run (default):
      python scripts/dev/clean.py
  - Actually delete files/dirs:
      python scripts/dev/clean.py --apply
  - Include heavy items (like .venv, node_modules if any):
      python scripts/dev/clean.py --apply --all
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[2]


def iter_matches(patterns: Iterable[str]) -> Iterable[Path]:
    """Yield paths matching the provided glob patterns, relative to ROOT.

    Patterns can match files or directories. Hidden items are included if
    explicitly matched by the pattern (e.g., ".pytest_cache/").
    """
    for pat in patterns:
        # Use rglob for recursive patterns, glob for top-level patterns
        # Always anchor to ROOT
        if any(ch in pat for ch in ["/", "\\", "**", "*"]):
            yield from ROOT.rglob(pat)
        else:
            yield from ROOT.glob(pat)


def unique_existing(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    result: List[Path] = []
    for p in paths:
        try:
            rp = p.resolve()
        except Exception:
            # Skip odd Windows device names, etc.
            continue
        if rp in seen:
            continue
        if rp.exists():
            seen.add(rp)
            result.append(rp)
    # Sort: longer paths first so nested files are removed before parents
    result.sort(key=lambda x: (len(str(x)), str(x)), reverse=True)
    return result


def delete_path(p: Path, apply: bool) -> None:
    rel = p.relative_to(ROOT)
    if p.is_dir():
        print(f"[DIR]  {rel}")
        if apply:
            shutil.rmtree(p, ignore_errors=True)
    else:
        print(f"[FILE] {rel}")
        if apply:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean caches and build outputs")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete files and directories (not just list)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include heavy/optional items (e.g., .venv)",
    )
    args = parser.parse_args()

    # Baseline patterns safe to remove
    patterns = [
        # Python caches and test artifacts
        "**/__pycache__",
        ".pytest_cache",
        "**/.pytest_cache",
        ".mypy_cache",
        "**/.mypy_cache",
        ".ruff_cache",
        "**/.ruff_cache",
        ".hypothesis",
        "**/.hypothesis",
        ".cache",
        "**/.cache",
        "htmlcov",
        "**/htmlcov",
        ".coverage",
        ".coverage.*",
        "coverage.xml",
        # Packaging/build artifacts
        "build",
        "dist",
        "*.egg-info",
        "**/*.egg-info",
        "pip-wheel-metadata",
        # Logs and temp files
        "**/*.log",
        "**/*.tmp",
        "**/*.temp",
        "**/*.bak",
        # Project-specific noisy folders
        "Unifiles/app/logs",
    ]

    # Optional heavy items
    if args.all:
        patterns.extend(
            [
                ".venv",
                "venv",
                "env",
                "ENV",
                "node_modules",
            ]
        )

    to_remove = unique_existing(iter_matches(patterns))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"unifiles clean: {mode}")
    print(f"Project root: {ROOT}")
    if not to_remove:
        print("Nothing to clean.")
        return 0

    for p in to_remove:
        delete_path(p, apply=args.apply)

    if not args.apply:
        print("\nNo changes made. Re-run with --apply to delete above items.")
    else:
        print("\nCleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
