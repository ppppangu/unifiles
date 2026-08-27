"""Regenerate server and SDK protocol code from the canonical OpenAPI document."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

GENERATOR_VERSION = "7.24.0"


def generator_environment() -> dict[str, str]:
    environment = dict(os.environ)
    homebrew_java = Path("/opt/homebrew/opt/openjdk/bin")
    if homebrew_java.exists():
        environment["PATH"] = f"{homebrew_java}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def generate(root: Path, config: str, output: Path, *, templates: Path | None = None) -> None:
    command = [
        str(root / "node_modules" / ".bin" / "openapi-generator-cli"),
        "generate",
        "--input-spec",
        str(root / "api" / "openapi.yaml"),
        "--config",
        str(root / "api" / "codegen" / config),
        "--output",
        str(output),
    ]
    if templates is not None:
        command.extend(["--template-dir", str(templates)])
    subprocess.run(command, check=True, cwd=root, env=generator_environment())
    actual_version = (output / ".openapi-generator" / "VERSION").read_text(encoding="utf-8").strip()
    if actual_version != GENERATOR_VERSION:
        raise RuntimeError(
            f"OpenAPI Generator {actual_version} produced {output}; expected {GENERATOR_VERSION}"
        )


def replace_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))


def mark_generated_typescript(source: Path) -> None:
    """Keep repository strictness while treating generator output as an external core."""

    for path in source.rglob("*.ts"):
        contents = path.read_text(encoding="utf-8")
        if not contents.startswith("// @ts-nocheck"):
            path.write_text(f"// @ts-nocheck\n{contents}", encoding="utf-8")


def mark_typed_python(package: Path) -> None:
    package.joinpath("py.typed").write_text("", encoding="utf-8")


def embed_contract(contract: Path, package: Path) -> None:
    document = yaml.safe_load(contract.read_text(encoding="utf-8"))
    package.joinpath("openapi.json").write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def record_contract_digest(contract: Path, output: Path) -> None:
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    output.joinpath(".openapi-generator", "CONTRACT_SHA256").write_text(
        f"{digest}\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-only", action="store_true")
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--typescript-only", action="store_true")
    options = parser.parse_args()
    root = Path(__file__).parents[1]
    selected = {
        name for name in ("server", "python", "typescript") if getattr(options, f"{name}_only")
    }
    targets = selected or {"server", "python", "typescript"}

    with tempfile.TemporaryDirectory(prefix="unifiles-codegen-") as temporary:
        work = Path(temporary)
        if "server" in targets:
            generated = work / "server"
            generate(
                root,
                "server-python.yaml",
                generated,
                templates=root / "api" / "codegen" / "templates" / "python-fastapi",
            )
            protocol_package = generated / "src" / "unifiles_server_protocol"
            mark_typed_python(protocol_package)
            embed_contract(root / "api" / "openapi.yaml", protocol_package)
            record_contract_digest(root / "api" / "openapi.yaml", generated)
            replace_directory(generated, root / "apps" / "server" / "generated")
        if "python" in targets:
            generated = work / "python"
            generate(root, "client-python.yaml", generated)
            mark_typed_python(generated / "unifiles_generated")
            record_contract_digest(root / "api" / "openapi.yaml", generated)
            replace_directory(generated, root / "packages" / "python" / "generated")
        if "typescript" in targets:
            generated = work / "typescript"
            generate(root, "client-typescript.yaml", generated)
            mark_generated_typescript(generated / "src")
            record_contract_digest(root / "api" / "openapi.yaml", generated)
            replace_directory(generated, root / "packages" / "typescript" / "generated")


if __name__ == "__main__":
    main()
