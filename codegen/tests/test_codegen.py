from __future__ import annotations

import copy
import json
import sys
import tomllib
from pathlib import Path

import pytest

CODEGEN_SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(CODEGEN_SCRIPTS))

from openapi_common import load_openapi, validate_openapi_invariants  # noqa: E402

import codegen as codegen_module  # noqa: E402


def test_manifest_targets_use_exact_output_allowlist() -> None:
    manifest = codegen_module.load_yaml(codegen_module.MANIFEST_PATH)
    targets = codegen_module.target_definitions(manifest)

    assert set(targets) == set(codegen_module.ALLOWED_OUTPUTS)
    for name, target in targets.items():
        assert codegen_module.resolve_repo_path(target["outputDir"]) == (
            codegen_module.resolve_repo_path(codegen_module.ALLOWED_OUTPUTS[name])
        )


def test_assert_within_rejects_sibling(tmp_path: Path) -> None:
    parent = tmp_path / "generated"
    with pytest.raises(codegen_module.CodegenError, match="Unsafe output path"):
        codegen_module.assert_within(tmp_path / "outside", parent)


def test_manifest_rejects_external_work_root() -> None:
    manifest = copy.deepcopy(codegen_module.load_yaml(codegen_module.MANIFEST_PATH))
    manifest["workRoot"] = "../outside"

    with pytest.raises(codegen_module.CodegenError, match="workRoot"):
        codegen_module.validate_manifest_ownership(
            manifest,
            codegen_module.target_definitions(manifest),
        )


def test_manifest_requires_supported_schema_version() -> None:
    manifest = copy.deepcopy(codegen_module.load_yaml(codegen_module.MANIFEST_PATH))
    manifest["version"] = 999

    with pytest.raises(codegen_module.CodegenError, match="version"):
        codegen_module.validate_manifest_ownership(
            manifest,
            codegen_module.target_definitions(manifest),
        )


@pytest.mark.parametrize(
    ("target_name", "field", "value", "message"),
    [
        ("sdk-python", "generatorName", "python-fastapi", "generator"),
        ("server-protocol-python", "templateDir", None, "template"),
        ("sdk-typescript", "postprocess", "sdk_python", "postprocessor"),
        ("sdk-python", "legacy", True, "legacy"),
    ],
)
def test_manifest_rejects_unowned_target_settings(
    target_name: str, field: str, value: object, message: str
) -> None:
    manifest = copy.deepcopy(codegen_module.load_yaml(codegen_module.MANIFEST_PATH))
    manifest["targets"][target_name][field] = value

    with pytest.raises(codegen_module.CodegenError, match=message):
        codegen_module.validate_manifest_ownership(
            manifest,
            codegen_module.target_definitions(manifest),
        )


def test_manifest_rejects_symlinked_output_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    outside = tmp_path / "outside"
    repository.joinpath("packages", "generated").mkdir(parents=True)
    outside.mkdir()
    repository.joinpath("packages", "generated", "sdk-python").symlink_to(
        outside,
        target_is_directory=True,
    )
    manifest = copy.deepcopy(codegen_module.load_yaml(codegen_module.MANIFEST_PATH))
    monkeypatch.setattr(codegen_module, "REPO_ROOT", repository)

    with pytest.raises(codegen_module.CodegenError, match="symlink component"):
        codegen_module.validate_manifest_ownership(
            manifest,
            codegen_module.target_definitions(manifest),
        )


def test_replace_refuses_unmarked_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codegen_module, "REPO_ROOT", tmp_path)
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    with pytest.raises(codegen_module.CodegenError, match="unmarked generated target"):
        codegen_module.replace_tree(source, destination, "sdk-python")

    assert source.exists()
    assert destination.exists()


def test_replace_refuses_wrong_target_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codegen_module, "REPO_ROOT", tmp_path)
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    destination.joinpath(".codegen-target.json").write_text(
        json.dumps({"target": "sdk-typescript"}),
        encoding="utf-8",
    )

    with pytest.raises(codegen_module.CodegenError, match="marker belongs"):
        codegen_module.replace_tree(source, destination, "sdk-python")


def test_replace_swaps_marked_target_and_cleans_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codegen_module, "REPO_ROOT", tmp_path)
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source.joinpath("new.txt").write_text("new", encoding="utf-8")
    destination.joinpath("old.txt").write_text("old", encoding="utf-8")
    destination.joinpath(".codegen-target.json").write_text(
        json.dumps({"target": "sdk-python"}),
        encoding="utf-8",
    )

    codegen_module.replace_tree(source, destination, "sdk-python")

    assert destination.joinpath("new.txt").read_text(encoding="utf-8") == "new"
    assert not destination.joinpath("old.txt").exists()
    assert not tmp_path.joinpath(".destination.backup").exists()


def test_replace_rolls_back_when_source_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codegen_module, "REPO_ROOT", tmp_path)
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    destination.joinpath("old.txt").write_text("old", encoding="utf-8")
    destination.joinpath(".codegen-target.json").write_text(
        json.dumps({"target": "sdk-python"}),
        encoding="utf-8",
    )
    original_rename = Path.rename

    def fail_source_rename(path: Path, target: Path) -> Path:
        if path == source:
            raise OSError("simulated rename failure")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_source_rename)

    with pytest.raises(OSError, match="simulated rename failure"):
        codegen_module.replace_tree(source, destination, "sdk-python")

    assert destination.joinpath("old.txt").read_text(encoding="utf-8") == "old"
    assert source.exists()
    assert not tmp_path.joinpath(".destination.backup").exists()


def test_tree_hash_ignores_python_cache(tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = source / "__pycache__"
    cache.mkdir(parents=True)
    source.joinpath("code.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache.joinpath("code.cpython-313.pyc").write_bytes(b"first")
    initial = codegen_module.sha256_tree(source)

    cache.joinpath("code.cpython-313.pyc").write_bytes(b"second")

    assert codegen_module.sha256_tree(source) == initial


def test_file_manifest_ignores_package_build_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("package.json").write_text("{}\n", encoding="utf-8")
    expected = codegen_module.file_manifest(source)

    source.joinpath("dist").mkdir()
    source.joinpath("dist", "index.js").write_text("generated build", encoding="utf-8")
    source.joinpath("build").mkdir()
    source.joinpath("build", "wheel.whl").write_bytes(b"wheel")
    source.joinpath("node_modules").mkdir()
    source.joinpath("node_modules", "dependency.js").write_text("dependency", encoding="utf-8")
    source.joinpath("cache.tsbuildinfo").write_text("cache", encoding="utf-8")

    assert codegen_module.file_manifest(source) == expected


def test_contract_rejects_multiple_security_requirements() -> None:
    contract = load_openapi(
        codegen_module.REPO_ROOT / "contracts" / "openapi" / "unifiles.yaml"
    )
    contract["paths"]["/v1/files"]["get"]["security"] = [
        {"BearerAuth": []},
        {"AnotherScheme": []},
    ]

    with pytest.raises(ValueError, match="exactly one Security Requirement"):
        validate_openapi_invariants(contract)


def test_sdk_artifacts_and_handwritten_consumers_have_separate_roots() -> None:
    root = codegen_module.REPO_ROOT
    generated_python = root / "packages" / "generated" / "sdk-python"
    generated_typescript = root / "packages" / "generated" / "sdk-typescript"

    assert generated_python.joinpath(".codegen-target.json").exists()
    assert generated_typescript.joinpath(".codegen-target.json").exists()
    assert not root.joinpath("packages", "python", "generated").exists()
    assert not root.joinpath("packages", "typescript", "generated").exists()
    assert root.joinpath("apps", "cli", "package.json").exists()
    assert not root.joinpath("packages", "cli").exists()

    generated_python_project = tomllib.loads(
        generated_python.joinpath("pyproject.toml").read_text(encoding="utf-8")
    )
    public_python_project = tomllib.loads(
        root.joinpath("packages", "python", "pyproject.toml").read_text(encoding="utf-8")
    )
    assert generated_python_project["project"]["name"] == "unifiles-generated"
    assert "unifiles-generated==0.1.0" in public_python_project["project"]["dependencies"]
    assert public_python_project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/unifiles"
    ]

    generated_typescript_package = json.loads(
        generated_typescript.joinpath("package.json").read_text(encoding="utf-8")
    )
    public_typescript_package = json.loads(
        root.joinpath("packages", "typescript", "package.json").read_text(encoding="utf-8")
    )
    assert generated_typescript_package["name"] == "@wyy/unifiles-generated"
    assert public_typescript_package["dependencies"]["@wyy/unifiles-generated"] == "0.1.0"
