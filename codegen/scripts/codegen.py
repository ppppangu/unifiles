"""Safely generate, validate, and compare manifest-owned OpenAPI artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from openapi_common import UniqueKeyLoader, validate_openapi_invariants

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "codegen" / "manifest.yaml"
ALLOWED_OUTPUTS = {
    "server-protocol-python": "packages/generated/server-protocol-python",
    "sdk-python": "packages/generated/sdk-python",
    "sdk-typescript": "packages/generated/sdk-typescript",
}
ALLOWED_CONFIGS = {
    "server-protocol-python": "codegen/configs/server-protocol-python.yaml",
    "sdk-python": "codegen/configs/sdk-python.yaml",
    "sdk-typescript": "codegen/configs/sdk-typescript.yaml",
}
ALLOWED_GENERATORS = {
    "server-protocol-python": "python-fastapi",
    "sdk-python": "python",
    "sdk-typescript": "typescript-fetch",
}
ALLOWED_TEMPLATES = {
    "server-protocol-python": "codegen/templates/python-fastapi",
    "sdk-python": None,
    "sdk-typescript": None,
}
ALLOWED_POSTPROCESSORS = {
    "server-protocol-python": "server_protocol_python",
    "sdk-python": "sdk_python",
    "sdk-typescript": "sdk_typescript",
}
EXPECTED_GENERATED_ROOT = "packages/generated"
EXPECTED_WORK_ROOT = ".codegen-work"
EXPECTED_SPEC = "contracts/openapi/unifiles.yaml"
EXPECTED_VERSION_FILE = "codegen/VERSION"
EXPECTED_TOOL_COMMAND = ["./node_modules/.bin/openapi-generator-cli"]
IGNORED_BUILD_COMPONENTS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "node_modules",
}


class CodegenError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    if not isinstance(value, dict):
        raise CodegenError(f"Expected a mapping in {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_files(path: Path) -> Iterator[Path]:
    return (
        item
        for item in path.rglob("*")
        if item.is_file()
        and not IGNORED_BUILD_COMPONENTS.intersection(item.relative_to(path).parts)
        and not any(part.endswith(".egg-info") for part in item.relative_to(path).parts)
        and item.suffix != ".pyc"
        and item.suffix != ".tsbuildinfo"
        and item.name != ".DS_Store"
    )


def sha256_tree(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    digest = hashlib.sha256()
    for file in sorted(stable_files(path)):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(file)))
    return digest.hexdigest()


def file_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        file.relative_to(path).as_posix(): sha256_file(file)
        for file in sorted(stable_files(path))
    }


def resolve_repo_path(value: object) -> Path:
    return Path(os.path.abspath(REPO_ROOT / str(value)))


def assert_within(child: Path, parent: Path) -> None:
    try:
        child.relative_to(parent)
    except ValueError as error:
        raise CodegenError(f"Unsafe output path: {child} is outside {parent}") from error


def assert_no_symlink_components(path: Path, *, label: str) -> None:
    assert_within(path, REPO_ROOT)
    current = REPO_ROOT
    for component in path.relative_to(REPO_ROOT).parts:
        current = current / component
        if current.is_symlink():
            raise CodegenError(f"{label} contains a symlink component: {current}")


def read_expected_version(manifest: dict[str, Any]) -> str:
    path = resolve_repo_path(manifest["tool"]["versionFile"])
    version = path.read_text(encoding="utf-8").strip()
    if not version:
        raise CodegenError(f"Empty generator version file: {path}")
    return version


def tool_command(manifest: dict[str, Any]) -> list[str]:
    value = manifest["tool"]["command"]
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise CodegenError("tool.command must be a non-empty string list")
    command = list(value)
    executable = resolve_repo_path(command[0])
    command[0] = str(executable)
    return command


def actual_generator_version(command: list[str]) -> str:
    result = subprocess.run(
        [*command, "version"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise CodegenError("OpenAPI Generator returned an empty version")
    return lines[-1]


def validate_contract_source(command: list[str], spec: Path) -> None:
    value = yaml.load(spec.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    if not isinstance(value, dict):
        raise CodegenError(f"OpenAPI document must be a mapping: {spec}")
    try:
        validate_openapi_invariants(value)
    except ValueError as error:
        raise CodegenError(str(error)) from error
    subprocess.run(
        [*command, "validate", "--input-spec", str(spec)],
        cwd=REPO_ROOT,
        check=True,
    )


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def postprocess_server_protocol(output: Path, spec: Path) -> None:
    package = output / "src" / "unifiles_server_protocol"
    package.joinpath("__init__.py").write_text(
        '"""Generated protocol package for the Unifiles API."""\n',
        encoding="utf-8",
    )
    package.joinpath("py.typed").write_text("", encoding="utf-8")

    document = yaml.load(spec.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    package.joinpath("openapi.json").write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    package.joinpath("main.py").unlink(missing_ok=True)
    for relative in (
        ".flake8",
        ".gitignore",
        ".openapi-generator",
        ".openapi-generator-ignore",
        "Dockerfile",
        "docker-compose.yaml",
        "openapi.yaml",
        "requirements.txt",
        "setup.cfg",
        "tests",
    ):
        remove_path(output / relative)

    output.joinpath("pyproject.toml").write_text(
        """[build-system]
requires = ["hatchling>=1.27.0"]
build-backend = "hatchling.build"

[project]
name = "unifiles-server-protocol"
version = "0.1.0"
description = "Generated FastAPI protocol package for the Unifiles API"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}
dependencies = [
    "fastapi>=0.115.0",
    "pydantic>=2.10.0",
    "python-multipart>=0.0.20",
    "typing-extensions>=4.12.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/unifiles_server_protocol"]
""",
        encoding="utf-8",
    )
    output.joinpath("README.md").write_text(
        """# unifiles-server-protocol

Generated FastAPI protocol package for the UniFiles API.

This artifact contains transport DTOs, Base API interfaces, generated route
adapters, the canonical OpenAPI JSON document, and PEP 561 type information.
It is a library consumed by unifiles-server; it is not a runnable server.

Do not edit files in this directory. Regenerate from the repository root:

    npm run generate

Build the package with:

    uv build --package unifiles-server-protocol

Generated route factories receive implementation and security providers from
the consuming application. This package never imports unifiles_server.
""",
        encoding="utf-8",
    )


def record_contract_digest(output: Path, spec: Path) -> None:
    metadata = output / ".openapi-generator"
    metadata.mkdir(parents=True, exist_ok=True)
    metadata.joinpath("CONTRACT_SHA256").write_text(
        f"{sha256_file(spec)}\n",
        encoding="utf-8",
    )


def postprocess_sdk_python(output: Path, spec: Path) -> None:
    output.joinpath("unifiles_generated", "py.typed").write_text("", encoding="utf-8")
    record_contract_digest(output, spec)
    output.joinpath("unifiles_generated_README.md").unlink(missing_ok=True)
    output.joinpath("pyproject.toml").write_text(
        """[build-system]
requires = ["hatchling>=1.27.0"]
build-backend = "hatchling.build"

[project]
name = "unifiles-generated"
version = "0.1.0"
description = "Generated Python client core for the Unifiles API"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.10.0",
    "python-dateutil>=2.9.0",
    "typing-extensions>=4.12.0",
]

[tool.hatch.build.targets.wheel]
packages = ["unifiles_generated"]
""",
        encoding="utf-8",
    )
    output.joinpath("README.md").write_text(
        """# unifiles-generated

Generated Python transport client and DTO package for the UniFiles API.

This artifact is the mechanical OpenAPI projection consumed by the handwritten
`unifiles-client` facade. It can be built and tested independently, and it must
never contain handwritten SDK behavior.

Do not edit files in this directory. Regenerate from the repository root:

    uv run python codegen/scripts/codegen.py generate sdk-python

Build the package with:

    uv build --package unifiles-generated
""",
        encoding="utf-8",
    )


def postprocess_sdk_typescript(output: Path, spec: Path) -> None:
    for path in output.joinpath("src").rglob("*.ts"):
        contents = path.read_text(encoding="utf-8")
        if not contents.startswith("// @ts-nocheck"):
            path.write_text(f"// @ts-nocheck\n{contents}", encoding="utf-8")
    record_contract_digest(output, spec)
    package_path = output / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package.update(
        {
            "description": "Generated TypeScript client core for the Unifiles API",
            "license": "Apache-2.0",
            "repository": {
                "type": "git",
                "url": "https://github.com/ppppangu/unifiles.git",
                "directory": "packages/generated/sdk-typescript",
            },
            "files": ["dist", "README.md"],
            "engines": {"node": ">=22"},
        }
    )
    package_path.write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output.joinpath("README.md").write_text(
        """# @wyy/unifiles-generated

Generated TypeScript transport client and DTO package for the UniFiles API.

This artifact is the mechanical OpenAPI projection consumed at build time by
the handwritten `@wyy/unifiles` facade. It can be built and packed independently,
and it must never contain handwritten SDK behavior.

Do not edit files in this directory. Regenerate from the repository root:

    uv run python codegen/scripts/codegen.py generate sdk-typescript

Build the package with:

    npm run build --workspace @wyy/unifiles-generated
""",
        encoding="utf-8",
    )


POSTPROCESSORS = {
    "server_protocol_python": postprocess_server_protocol,
    "sdk_python": postprocess_sdk_python,
    "sdk_typescript": postprocess_sdk_typescript,
}


def build_marker(
    *,
    target_name: str,
    generator_version: str,
    spec: Path,
    config: Path,
    template_dir: Path | None,
) -> dict[str, str]:
    return {
        "codegenSha256": sha256_tree(REPO_ROOT / "codegen" / "scripts"),
        "configSha256": sha256_file(config),
        "generatorVersion": generator_version,
        "specSha256": sha256_file(spec),
        "target": target_name,
        "templateSha256": sha256_tree(template_dir),
    }


def validate_existing_target(destination: Path, target_name: str) -> None:
    marker_path = destination / ".codegen-target.json"
    if not marker_path.exists():
        raise CodegenError(f"Refusing to replace unmarked generated target: {destination}")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CodegenError(f"Invalid generated target marker: {marker_path}") from error
    if not isinstance(marker, dict):
        raise CodegenError(f"Invalid generated target marker: {marker_path}")
    if marker.get("target") != target_name:
        raise CodegenError(
            f"Refusing to replace {destination}: marker belongs to {marker.get('target')!r}"
        )


def replace_tree(source: Path, destination: Path, target_name: str) -> None:
    backup = destination.with_name(f".{destination.name}.backup")
    assert_no_symlink_components(destination, label="target output")
    assert_no_symlink_components(backup, label="target backup")
    if backup.exists() or backup.is_symlink():
        raise CodegenError(f"Stale codegen backup requires manual inspection: {backup}")
    if destination.exists() or destination.is_symlink():
        validate_existing_target(destination, target_name)
        destination.rename(backup)
    try:
        source.rename(destination)
    except Exception:
        remove_path(destination)
        if backup.exists():
            backup.rename(destination)
        raise
    else:
        remove_path(backup)


def target_definitions(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = manifest.get("targets")
    if not isinstance(value, dict):
        raise CodegenError("manifest.targets must be a mapping")
    if not all(isinstance(name, str) and isinstance(target, dict) for name, target in value.items()):
        raise CodegenError("Every target must be a named mapping")
    return value


def validate_manifest_ownership(
    manifest: dict[str, Any], targets: dict[str, dict[str, Any]]
) -> None:
    if type(manifest.get("version")) is not int or manifest.get("version") != 1:
        raise CodegenError("manifest version must be integer 1")

    generated_root = resolve_repo_path(manifest.get("generatedRoot"))
    work_root = resolve_repo_path(manifest.get("workRoot"))
    spec = resolve_repo_path(manifest.get("spec"))
    if generated_root != resolve_repo_path(EXPECTED_GENERATED_ROOT):
        raise CodegenError("generatedRoot must be packages/generated")
    if work_root != resolve_repo_path(EXPECTED_WORK_ROOT):
        raise CodegenError("workRoot must be the repository .codegen-work directory")
    if spec != resolve_repo_path(EXPECTED_SPEC):
        raise CodegenError("manifest spec path is not owned by contracts/openapi")
    assert_no_symlink_components(generated_root, label="generatedRoot")
    assert_no_symlink_components(work_root, label="workRoot")
    assert_no_symlink_components(spec, label="spec")

    tool = manifest.get("tool")
    if not isinstance(tool, dict):
        raise CodegenError("manifest.tool must be a mapping")
    version_file = resolve_repo_path(tool.get("versionFile"))
    if tool.get("command") != EXPECTED_TOOL_COMMAND:
        raise CodegenError("manifest tool command is not the repository-local generator")
    if version_file != resolve_repo_path(EXPECTED_VERSION_FILE):
        raise CodegenError("manifest version file must be codegen/VERSION")
    assert_no_symlink_components(version_file, label="version file")

    if set(targets) != set(ALLOWED_OUTPUTS):
        raise CodegenError("manifest targets do not match the exact target allowlist")
    for name, target in targets.items():
        destination = resolve_repo_path(target.get("outputDir"))
        config = resolve_repo_path(target.get("config"))
        if destination != resolve_repo_path(ALLOWED_OUTPUTS[name]):
            raise CodegenError(f"Target {name} has an unsafe output directory")
        if config != resolve_repo_path(ALLOWED_CONFIGS[name]):
            raise CodegenError(f"Target {name} has an unexpected config path")
        if target.get("generatorName") != ALLOWED_GENERATORS[name]:
            raise CodegenError(f"Target {name} has an unexpected generator")
        expected_template = ALLOWED_TEMPLATES[name]
        actual_template = target.get("templateDir")
        if actual_template != expected_template:
            raise CodegenError(f"Target {name} has an unexpected template directory")
        if target.get("postprocess") != ALLOWED_POSTPROCESSORS[name]:
            raise CodegenError(f"Target {name} has an unexpected postprocessor")
        if "legacy" in target:
            raise CodegenError(f"Target {name} must not declare legacy mode")
        assert_no_symlink_components(destination, label=f"{name} output")
        assert_no_symlink_components(config, label=f"{name} config")
        if expected_template is not None:
            assert_no_symlink_components(
                resolve_repo_path(expected_template),
                label=f"{name} template",
            )


def generate_target(
    manifest: dict[str, Any],
    target_name: str,
    *,
    check_only: bool,
) -> None:
    targets = target_definitions(manifest)
    validate_manifest_ownership(manifest, targets)
    if target_name not in targets:
        raise CodegenError(f"Unknown target: {target_name}")
    target = targets[target_name]

    generated_root = resolve_repo_path(manifest["generatedRoot"])
    work_root = resolve_repo_path(manifest["workRoot"])
    destination = resolve_repo_path(target["outputDir"])
    allowed_output = ALLOWED_OUTPUTS.get(target_name)
    if allowed_output is None or destination != resolve_repo_path(allowed_output):
        raise CodegenError(f"Target {target_name} does not own the declared output {destination}")
    assert_within(destination, generated_root)
    if destination == generated_root:
        raise CodegenError("A target may not own the entire generated root")

    spec = resolve_repo_path(manifest["spec"])
    config = resolve_repo_path(target["config"])
    template_value = target.get("templateDir")
    template_dir = resolve_repo_path(template_value) if template_value else None

    command = tool_command(manifest)
    expected_version = read_expected_version(manifest)
    actual_version = actual_generator_version(command)
    if actual_version != expected_version:
        raise CodegenError(
            f"Generator version mismatch: expected {expected_version}, got {actual_version}"
        )

    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = work_root / f"{target_name}-{uuid.uuid4().hex}"
    output = work_dir / target_name
    output.parent.mkdir(parents=True, exist_ok=True)

    generator_command = [
        *command,
        "generate",
        "--input-spec",
        str(spec),
        "--generator-name",
        str(target["generatorName"]),
        "--config",
        str(config),
        "--output",
        str(output),
    ]
    if template_dir is not None:
        generator_command.extend(["--template-dir", str(template_dir)])
    ignored_paths = target.get("ignorePaths", [])
    if ignored_paths:
        generator_command.extend(["--openapi-generator-ignore-list", ",".join(ignored_paths)])

    try:
        subprocess.run(generator_command, cwd=REPO_ROOT, check=True)

        postprocessor_name = target.get("postprocess")
        if postprocessor_name:
            postprocessor = POSTPROCESSORS.get(str(postprocessor_name))
            if postprocessor is None:
                raise CodegenError(f"Unknown postprocessor: {postprocessor_name}")
            postprocessor(output, spec)

        for required in target.get("requiredPaths", []):
            if not (output / str(required)).exists():
                raise CodegenError(f"{target_name} is missing required path: {required}")

        marker = build_marker(
            target_name=target_name,
            generator_version=actual_version,
            spec=spec,
            config=config,
            template_dir=template_dir,
        )
        output.joinpath(".codegen-target.json").write_text(
            json.dumps(marker, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if check_only:
            expected = file_manifest(destination)
            actual = file_manifest(output)
            if expected != actual:
                expected_files = set(expected)
                actual_files = set(actual)
                added = sorted(actual_files - expected_files)
                removed = sorted(expected_files - actual_files)
                changed = sorted(
                    name
                    for name in expected_files & actual_files
                    if expected[name] != actual[name]
                )
                raise CodegenError(
                    f"Generated target {target_name} is stale\n"
                    f"added={added}\nremoved={removed}\nchanged={changed}"
                )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            replace_tree(output, destination, target_name)
    finally:
        remove_path(work_dir)


def run_validation() -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "codegen" / "scripts" / "validate_contract.py")],
        cwd=REPO_ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("validate")
    for command_name in ("generate", "check"):
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("target")
    options = parser.parse_args()

    manifest = load_yaml(MANIFEST_PATH)
    targets = target_definitions(manifest)
    validate_manifest_ownership(manifest, targets)
    if options.command == "list":
        for name in sorted(targets):
            print(name)
        return 0
    if options.command == "validate":
        run_validation()
        return 0

    selected = sorted(targets) if options.target == "all" else [options.target]
    validate_contract_source(tool_command(manifest), resolve_repo_path(manifest["spec"]))
    for name in selected:
        generate_target(manifest, name, check_only=options.command == "check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CodegenError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
