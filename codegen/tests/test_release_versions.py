from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_release_versions import (  # noqa: E402
    COUPLED_DEPENDENCIES,
    NPM_REPOSITORIES,
    RELEASE_PACKAGES,
    REPO_ROOT,
    ReleaseVersionError,
    package_version,
    validate_npm_repository,
    validate_release_tag,
)


@pytest.mark.parametrize("kind", sorted(RELEASE_PACKAGES))
def test_current_release_artifacts_have_coupled_versions(kind: str) -> None:
    first_path, first_type = RELEASE_PACKAGES[kind][0]
    version = package_version(REPO_ROOT, first_path, first_type)

    assert validate_release_tag(f"{kind}-v{version}") == [
        path for path, _file_type in RELEASE_PACKAGES[kind]
    ]


def test_release_tag_rejects_a_version_mismatch() -> None:
    with pytest.raises(ReleaseVersionError, match="expects"):
        validate_release_tag("python-v999.0.0")


def test_release_tag_rejects_an_unknown_kind() -> None:
    with pytest.raises(ReleaseVersionError, match="Unsupported release tag"):
        validate_release_tag("unknown-v0.1.0")


@pytest.mark.parametrize("kind", sorted(COUPLED_DEPENDENCIES))
def test_release_tag_rejects_a_stale_exact_dependency(kind: str, tmp_path: Path) -> None:
    for relative_path, _file_type in RELEASE_PACKAGES[kind]:
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((REPO_ROOT / relative_path).read_text(encoding="utf-8"), encoding="utf-8")

    dependency_path, file_type, dependency_name = COUPLED_DEPENDENCIES[kind]
    dependency_file = tmp_path / dependency_path
    first_path, first_type = RELEASE_PACKAGES[kind][0]
    version = package_version(REPO_ROOT, first_path, first_type)
    if file_type == "toml":
        current = f'"{dependency_name}=={version}"'
        contents = dependency_file.read_text(encoding="utf-8")
        assert current in contents
        dependency_file.write_text(
            contents.replace(current, f'"{dependency_name}==999.0.0"'),
            encoding="utf-8",
        )
    else:
        document = json.loads(dependency_file.read_text(encoding="utf-8"))
        document["dependencies"][dependency_name] = "999.0.0"
        dependency_file.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseVersionError, match="exact dependency"):
        validate_release_tag(f"{kind}-v{version}", root=tmp_path)


@pytest.mark.parametrize(("relative_path", "directory"), sorted(NPM_REPOSITORIES.items()))
def test_npm_packages_declare_trusted_publishing_repository(
    relative_path: str,
    directory: str,
) -> None:
    validate_npm_repository(REPO_ROOT, relative_path, directory)


def test_npm_repository_mismatch_is_rejected(tmp_path: Path) -> None:
    relative_path, directory = next(iter(NPM_REPOSITORIES.items()))
    destination = tmp_path / relative_path
    destination.parent.mkdir(parents=True)
    document = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    document["repository"]["url"] = "https://github.com/example/wrong.git"
    destination.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReleaseVersionError, match="repository mismatch"):
        validate_npm_repository(tmp_path, relative_path, directory)
