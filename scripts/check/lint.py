#!/usr/bin/env python3
"""
Code linting script using ruff and mypy.
Performs comprehensive code quality checks for Python code.
"""

import os
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
        print(f"✅ {description} passed")
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
    Main function for code linting.

    Returns:
        0 if all critical checks pass, 1 otherwise
    """
    project_root = Path(__file__).parent.parent.parent
    print(f"📁 Project root: {project_root}")

    # Change to project root directory
    os.chdir(project_root)

    success = True

    # 1. Ruff code linting
    print("\n🔍 Running ruff code linting...")
    if not run_command(["uv", "run", "ruff", "check", "."], "Ruff code linting"):
        success = False

    # 2. Ruff format checking
    print("\n🎨 Checking code formatting...")
    if not run_command(
        ["uv", "run", "ruff", "format", "--check", "."], "Ruff format check"
    ):
        success = False

    # 3. MyPy type checking (non-critical)
    print("\n🔬 Running MyPy type checking...")
    if not run_command(
        ["uv", "run", "mypy", "unifiles/", "--config-file=mypy.ini"], "MyPy type check"
    ):
        print("⚠️  MyPy type checking failed but continuing...")

    if success:
        print("\n🎉 All code quality checks passed!")
        return 0
    print("\n💥 Code quality issues found, please fix before committing")
    return 1


if __name__ == "__main__":
    sys.exit(main())
