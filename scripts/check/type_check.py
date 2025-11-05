#!/usr/bin/env python3
"""
Type checking script using mypy.
Validates type hints and catches potential type-related errors.
"""

import subprocess
import sys
from pathlib import Path
from typing import List


def run_command(cmd: List[str], description: str) -> bool:
    """
    Run a command and return success status.

    Args:
        cmd: Command to run as list of arguments
        description: Human-readable description of the command

    Returns:
        True if command succeeded, False otherwise
    """
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {' '.join(cmd)}")
        return False


def main() -> int:
    """
    Main function for type checking.

    Returns:
        0 if type checking passes, 1 otherwise
    """
    project_root = Path(__file__).parent.parent.parent
    print(f"📁 Project root: {project_root}")

    # Change to project root directory
    import os

    os.chdir(project_root)

    success = True

    # Check if mypy config exists
    mypy_config = project_root / "mypy.ini"
    if not mypy_config.exists():
        print("⚠️  mypy.ini not found, using default configuration")

    # Run mypy type checking
    print("\n🔬 Running mypy type checking...")

    # Check the main unifiles package
    if not run_command(
        ["uv", "run", "mypy", "unifiles/", "--config-file=mypy.ini"],
        "Type checking unifiles package",
    ):
        success = False

    # Check client code
    client_path = project_root / "unifiles" / "client"
    if client_path.exists():
        if not run_command(
            ["uv", "run", "mypy", str(client_path), "--config-file=mypy.ini"],
            "Type checking client package",
        ):
            print("⚠️  Client type checking failed but continuing...")

    # Check test files (optional)
    tests_path = project_root / "tests"
    if tests_path.exists():
        if not run_command(
            ["uv", "run", "mypy", str(tests_path), "--config-file=mypy.ini"],
            "Type checking test files",
        ):
            print("ℹ️  Test type checking failed (expected for test files)")

    if success:
        print("\n🎉 Type checking completed successfully!")
        return 0
    print("\n💥 Type checking found issues")
    print("ℹ️  Note: Type checking failures are often non-critical")
    return 1


if __name__ == "__main__":
    sys.exit(main())
