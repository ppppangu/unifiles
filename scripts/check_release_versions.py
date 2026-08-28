"""Validate a release tag against every coupled package version."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_PACKAGES = {
    "python": (
        ("packages/generated/sdk-python/pyproject.toml", "toml"),
        ("packages/python/pyproject.toml", "toml"),
    ),
    "server": (
        ("packages/generated/server-protocol-python/pyproject.toml", "toml"),
        ("apps/server/pyproject.toml", "toml"),
    ),
    "typescript": (
        ("packages/generated/sdk-typescript/package.json", "json"),
        ("packages/typescript/package.json", "json"),
    ),
    "cli": (("apps/cli/package.json", "json"),),
}
COUPLED_DEPENDENCIES = {
    "python": ("packages/python/pyproject.toml", "toml", "unifiles-generated"),
    "server": ("apps/server/pyproject.toml", "toml", "unifiles-server-protocol"),
    "typescript": (
        "packages/typescript/package.json",
        "json",
        "@wyy/unifiles-generated",
    ),
}
EXPECTED_REPOSITORY_URL = "https://github.com/ppppangu/unifiles.git"
NPM_REPOSITORIES = {
    "packages/generated/sdk-typescript/package.json": "packages/generated/sdk-typescript",
    "packages/typescript/package.json": "packages/typescript",
    "apps/cli/package.json": "apps/cli",
}


class ReleaseVersionError(ValueError):
    """Raised when a tag and its release artifacts disagree."""


def package_document(root: Path, relative_path: str, file_type: str) -> dict[str, Any]:
    path = root / relative_path
    if file_type == "toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseVersionError(f"Package document must be an object: {relative_path}")
    return value


def package_version(root: Path, relative_path: str, file_type: str) -> str:
    document = package_document(root, relative_path, file_type)
    value = (
        document.get("project", {}).get("version")
        if file_type == "toml"
        else document.get("version")
    )
    if not isinstance(value, str) or not value:
        raise ReleaseVersionError(f"Missing package version: {relative_path}")
    return value


def validate_exact_dependency(
    root: Path,
    relative_path: str,
    file_type: str,
    dependency_name: str,
    expected_version: str,
) -> None:
    document = package_document(root, relative_path, file_type)
    if file_type == "toml":
        dependencies = document.get("project", {}).get("dependencies", [])
        expected = f"{dependency_name}=={expected_version}"
        actual_entries = [
            value
            for value in dependencies
            if isinstance(value, str) and value.startswith(dependency_name)
        ]
        actual: object = actual_entries
        valid = actual_entries == [expected]
    else:
        dependencies = document.get("dependencies", {})
        actual_value = dependencies.get(dependency_name) if isinstance(dependencies, dict) else None
        actual = actual_value
        expected = expected_version
        valid = actual_value == expected
    if not valid:
        raise ReleaseVersionError(
            f"Release requires exact dependency {dependency_name}=={expected_version} "
            f"in {relative_path}, found {actual!r}"
        )


def validate_npm_repository(root: Path, relative_path: str, expected_directory: str) -> None:
    document = package_document(root, relative_path, "json")
    repository = document.get("repository")
    expected = {
        "type": "git",
        "url": EXPECTED_REPOSITORY_URL,
        "directory": expected_directory,
    }
    if repository != expected:
        raise ReleaseVersionError(
            f"npm trusted publishing repository mismatch in {relative_path}: "
            f"expected {expected!r}, found {repository!r}"
        )


def validate_release_tag(tag: str, *, root: Path = REPO_ROOT) -> list[str]:
    kind, separator, expected = tag.partition("-v")
    if not separator or kind not in RELEASE_PACKAGES or not expected:
        allowed = ", ".join(f"{name}-v<version>" for name in RELEASE_PACKAGES)
        raise ReleaseVersionError(f"Unsupported release tag {tag!r}; expected one of: {allowed}")

    checked: list[str] = []
    for relative_path, file_type in RELEASE_PACKAGES[kind]:
        actual = package_version(root, relative_path, file_type)
        if actual != expected:
            raise ReleaseVersionError(
                f"Release tag {tag!r} expects {relative_path} version {expected}, found {actual}"
            )
        checked.append(relative_path)
        expected_directory = NPM_REPOSITORIES.get(relative_path)
        if expected_directory is not None:
            validate_npm_repository(root, relative_path, expected_directory)

    dependency = COUPLED_DEPENDENCIES.get(kind)
    if dependency is not None:
        validate_exact_dependency(root, *dependency, expected)
    return checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    options = parser.parse_args()
    checked = validate_release_tag(options.tag)
    print(f"Release version is consistent for {options.tag}: {', '.join(checked)}")


if __name__ == "__main__":
    main()
