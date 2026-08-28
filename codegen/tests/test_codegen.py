from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

CODEGEN_SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(CODEGEN_SCRIPTS))

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
        ("sdk-python", "legacy", "false", "legacy"),
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
    repository.joinpath("packages", "python").mkdir(parents=True)
    outside.mkdir()
    repository.joinpath("packages", "python", "generated").symlink_to(
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
