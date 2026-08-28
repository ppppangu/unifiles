"""Check ownership and package metadata of built Python artifacts."""

from __future__ import annotations

import zipfile
from pathlib import Path


def only_wheel(dist: Path, pattern: str) -> Path:
    wheels = sorted(dist.glob(pattern))
    if len(wheels) != 1:
        raise SystemExit(f"expected one wheel matching {pattern}, found {wheels}")
    return wheels[0]


def main() -> None:
    root = Path(__file__).parents[2]
    dist = root / "dist"
    protocol_wheel = only_wheel(dist, "unifiles_server_protocol-*.whl")
    server_wheel = only_wheel(dist, "unifiles_server-*.whl")

    with zipfile.ZipFile(protocol_wheel) as archive:
        names = set(archive.namelist())
        required = {
            "unifiles_server_protocol/openapi.json",
            "unifiles_server_protocol/py.typed",
        }
        missing = required - names
        if missing:
            raise SystemExit(f"protocol wheel is missing files: {sorted(missing)}")
        if not any(name.startswith("unifiles_server_protocol/apis/") for name in names):
            raise SystemExit("protocol wheel is missing generated APIs")
        if not any(name.startswith("unifiles_server_protocol/models/") for name in names):
            raise SystemExit("protocol wheel is missing generated models")

    with zipfile.ZipFile(server_wheel) as archive:
        names = set(archive.namelist())
        if any(name.startswith("unifiles_server_protocol/") for name in names):
            raise SystemExit("server wheel must not embed the protocol package")
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")),
            None,
        )
        if metadata_name is None:
            raise SystemExit("server wheel has no METADATA")
        metadata = archive.read(metadata_name).decode()
        if "Requires-Dist: unifiles-server-protocol==0.1.0" not in metadata:
            raise SystemExit("server wheel does not declare the protocol dependency")

    print("Python artifact boundaries are valid")


if __name__ == "__main__":
    main()
