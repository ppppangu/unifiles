#!/usr/bin/env python3
"""
Rename schema references from unifiles to unifiles across the project.

- Recursively scans files under a given root
- Applies precise, order-aware replacements for schema usage
- Handles:
  * qualifier: unifiles.table -> unifiles.table
  * quoted qualifier: "unifiles".table -> "unifiles".table
  * CREATE/ALTER/GRANT/REVOKE ... SCHEMA unifiles -> ... SCHEMA unifiles
  * SET search_path TO ... unifiles ... -> replace that item with unifiles
  * String literal usages related to schema: 'unifiles' -> 'unifiles'
  * Also updates comments and markdown if included
- Skips binary files; configurable by extensions
- Writes backups to backup_schema_rename_YYYYMMDD_HHMMSS/

Usage:
  python scripts/tools/rename_schema.py --root . --include-md --include-py
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple

# Regex patterns compiled once
# 1) Schema qualifier (unquoted and quoted)
RE_QUALIFIER_UNQUOTED = re.compile(r"(?i)\bunifiles\b\.")
RE_QUALIFIER_QUOTED = re.compile(r"(?i)\"unifiles\"\.")

# 2) SCHEMA keyword contexts (CREATE/ALTER/GRANT/REVOKE/ON SCHEMA)
RE_ON_SCHEMA = re.compile(r"(?i)\b(ON\s+SCHEMA|SCHEMA)\s+(\"?)unifiles\2\b")

# 3) search_path
RE_SEARCH_PATH = re.compile(r"(?is)(SET\s+search_path\s+TO\s+)([^;]+)(;?)")
RE_SCHEMA_ITEM = re.compile(r"(?i)(\s*)(\"?)unifiles\2(\s*)(,?)(\s*)")

# 4) string literals for schema name (common in views/functions/monitor queries)
RE_SINGLE_QUOTED_SCHEMA = re.compile(r"(?i)'unifiles'")
RE_DOUBLE_QUOTED_SCHEMA = re.compile(r'(?i)"unifiles"')

# 5) Bare schema word (fallback) - use sparingly, after more specific ones
RE_BARE_SCHEMA_WORD = re.compile(r"(?i)\bunifiles\b")

DEFAULT_EXTS = {
    ".sql",
    ".psql",
    ".sql.j2",
    ".jinja2",
    ".j2",
    ".tpl",
}
MD_EXTS = {".md", ".markdown"}
CODE_EXTS = {".py"}

SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "env", ".ruff_cache", ".mypy_cache"}


def should_process_file(path: Path, allow_md: bool, allow_code: bool) -> bool:
    ext = path.suffix.lower()
    if ext in DEFAULT_EXTS:
        return True
    if allow_md and ext in MD_EXTS:
        return True
    if allow_code and ext in CODE_EXTS:
        return True
    # handle multi-suffix like .sql.j2
    name = path.name.lower()
    if any(name.endswith(suf) for suf in (".sql.j2", ".jinja2")):
        return True
    return False


def iter_files(root: Path, allow_md: bool, allow_code: bool) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith("backup_schema_rename_")
        ]
        for fn in filenames:
            p = Path(dirpath) / fn
            if should_process_file(p, allow_md, allow_code):
                yield p


def replace_search_path(match: re.Match) -> str:
    prefix, list_part, suffix = match.group(1), match.group(2), match.group(3)

    def sub_item(m: re.Match) -> str:
        # Preserve original spacing and quoting
        pre_ws, quote, post_ws, comma_opt, tail_ws = m.groups()
        return f"{pre_ws}{quote}unifiles{quote}{post_ws}{comma_opt}{tail_ws}"

    new_list = RE_SCHEMA_ITEM.sub(sub_item, list_part)
    return f"{prefix}{new_list}{suffix}"


def apply_rewrites(text: str) -> Tuple[str, int]:
    count = 0

    def subn(pattern: re.Pattern, repl) -> None:
        nonlocal text, count
        new_text, n = pattern.subn(repl, text)
        if n:
            text = new_text
            count += n

    # Order matters: from most specific to more general
    subn(RE_QUALIFIER_QUOTED, '"unifiles".')
    subn(RE_QUALIFIER_UNQUOTED, "unifiles.")

    # SCHEMA keyword contexts
    def repl_on_schema(m: re.Match) -> str:
        kw = m.group(1)
        quote = m.group(2) or ""
        return f"{kw} {quote}unifiles{quote}"

    subn(RE_ON_SCHEMA, repl_on_schema)

    # search_path lists
    subn(RE_SEARCH_PATH, replace_search_path)

    # string literal schema
    subn(RE_SINGLE_QUOTED_SCHEMA, "'unifiles'")
    subn(RE_DOUBLE_QUOTED_SCHEMA, '"unifiles"')

    # Fallback: bare word (only for .sql-like files and markdown; not for code unless explicitly allowed)
    # We'll leave this handled by caller when appropriate.

    return text, count


def process_file(
    src: Path, backup_root: Path, allow_bare_word: bool
) -> Tuple[bool, int]:
    raw = src.read_text(encoding="utf-8", errors="ignore")
    new, n_changes = apply_rewrites(raw)

    # Bare word fallback if no changes from above AND allowed
    if allow_bare_word:
        new2, n2 = RE_BARE_SCHEMA_WORD.subn("unifiles", new)
        n_changes += n2
        new = new2

    if n_changes:
        # backup
        dst_backup = backup_root / src.relative_to(backup_root.parent)
        dst_backup.parent.mkdir(parents=True, exist_ok=True)
        dst_backup.write_text(raw, encoding="utf-8")
        # write new
        src.write_text(new, encoding="utf-8")
        return True, n_changes
    return False, 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rename schema references from unifiles to unifiles"
    )
    ap.add_argument(
        "--root", default=Path.cwd(), type=Path, help="Root directory to process"
    )
    ap.add_argument(
        "--include-md", action="store_true", help="Also process markdown and docs"
    )
    ap.add_argument(
        "--include-py",
        action="store_true",
        help="Also process Python files (dynamic SQL)",
    )
    ap.add_argument(
        "--allow-bare",
        action="store_true",
        help="Allow replacing bare word 'unifiles' to 'unifiles' as fallback",
    )
    args = ap.parse_args()

    root: Path = args.root.resolve()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / f"backup_schema_rename_{ts}"

    # Prepare backup root by mirroring structure at write time
    changed_files: List[Tuple[Path, int]] = []

    files = list(iter_files(root, allow_md=args.include_md, allow_code=args.include_py))
    for p in files:
        # compute backup path base (root parent relationship)
        # backup will have the same relative structure under backup_root
        backup_base_parent = backup_root.parent if backup_root.parent == root else root
        # process
        changed, n = process_file(p, backup_root, allow_bare_word=args.allow_bare)
        if changed:
            changed_files.append((p, n))

    print(f"Processed files: {len(files)}")
    print(f"Changed files: {len(changed_files)}")
    total_changes = sum(n for _, n in changed_files)
    print(f"Total replacements: {total_changes}")
    for path, n in sorted(changed_files, key=lambda x: str(x[0])):
        print(f"{path}  (+{n})")

    print(f"Backup directory: {backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
