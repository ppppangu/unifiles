#!/usr/bin/env python3
"""
Code formatting script using ruff.
Automatically formats Python code according to project standards.
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
    Main function that runs code formatting.

    Returns:
        0 if formatting succeeds, 1 otherwise
    """
    project_root = Path(__file__).parent.parent
    print(f"📁 Project root: {project_root}")

    # Change to project root directory
    os.chdir(project_root)

    success = True

    # 1. Use ruff to check and auto-fix issues
    print("\n🔍 Running ruff checks with auto-fix...")
    if not run_command(["uv", "run", "ruff", "check", ".", "--fix"], "Ruff auto-fix"):
        success = False

    # 2. Format code with ruff
    print("\n🎨 Formatting code with ruff...")
    if not run_command(["uv", "run", "ruff", "format", "."], "Ruff formatting"):
        success = False

    if success:
        print("\n🎉 Code formatting completed successfully!")
        return 0
    print("\n💥 Code formatting encountered errors")
    return 1


if __name__ == "__main__":
    sys.exit(main())
