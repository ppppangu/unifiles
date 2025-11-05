#!/usr/bin/env python3
"""
Global find-and-replace utility for renaming schema (or any token) across the project.

By default, replaces all occurrences of 'unifiles' with 'unifiles' in all
UTF-8 text files under --root, skipping common binary directories and files.

Features:
- Recursive traversal with skip-lists for common binary/venv/git folders
- Backup original files into backup_global_replace_YYYYMMDD_HHMMSS/
- Dry-run mode to preview changes
- Optional custom pattern/replacement

Usage examples:
  uv run python scripts/tools/global_replace_schema.py --root .
  uv run python scripts/tools/global_replace_schema.py --root . --dry-run
  uv run python scripts/tools/global_replace_schema.py --root . --pattern unifiles --replacement unifiles
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Iterable, List, Tuple

DEFAULT_PATTERN = "unifiles"
DEFAULT_REPLACEMENT = "unifiles"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
}
SKIP_DIR_PREFIXES = (
    "backup_schema_rename_",
    "backup_global_replace_",
)

# Common binary file extensions to skip
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".pdf",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".dll",
    ".exe",
    ".bin",
    ".so",
    ".dylib",
    ".pyd",
}


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIRS
            and not any(d.startswith(pfx) for pfx in SKIP_DIR_PREFIXES)
        ]
        for fn in filenames:
            p = Path(dirpath) / fn
            # skip binary-looking extensions
            if p.suffix.lower() in BINARY_EXTS:
                continue
            yield p


def process_file(
    path: Path, pattern: str, replacement: str, backup_root: Path, dry_run: bool
) -> Tuple[bool, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Non-UTF8 file; skip to be safe
        return False, 0
    count = text.count(pattern)
    if count == 0:
        return False, 0

    if dry_run:
        return True, count

    new_text = text.replace(pattern, replacement)

    # backup original
    backup_target = backup_root / path.relative_to(backup_root.parent)
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    backup_target.write_text(text, encoding="utf-8")

    # write updated
    path.write_text(new_text, encoding="utf-8")
    return True, count


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Global find-and-replace across the project"
    )
    ap.add_argument(
        "--root", default=Path.cwd(), type=Path, help="Root directory to process"
    )
    ap.add_argument(
        "--pattern", default=DEFAULT_PATTERN, help="Pattern to find (default: unifiles)"
    )
    ap.add_argument(
        "--replacement",
        default=DEFAULT_REPLACEMENT,
        help="Replacement string (default: unifiles)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing files"
    )
    args = ap.parse_args()

    root = args.root.resolve()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / f"backup_global_replace_{ts}"

    changed: List[Tuple[Path, int]] = []

    files = list(iter_files(root))
    for p in files:
        did, n = process_file(
            p, args.pattern, args.replacement, backup_root, args.dry_run
        )
        if did:
            changed.append((p, n))

    print(f"Processed files: {len(files)}")
    print(f"Changed files: {len(changed)}")
    total = sum(n for _, n in changed)
    print(f"Total replacements: {total}")
    for p, n in sorted(changed, key=lambda x: str(x[0])):
        print(f"{p}  (+{n})")

    if not args.dry_run:
        print(f"Backup directory: {backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
