#!/usr/bin/env python3
"""
Test runner script.
Runs all project tests including unit tests, integration tests, and coverage analysis.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List


def run_command(cmd: List[str], description: str, critical: bool = True) -> bool:
    """
    Run a command and return success status.

    Args:
        cmd: Command to run as list of arguments
        description: Human-readable description of the command
        critical: Whether failure should fail the entire test run

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
        if not critical:
            print(f"⚠️  {description} failed but continuing...")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {' '.join(cmd)}")
        return False


def main() -> int:
    """
    Main function for running tests.

    Returns:
        0 if all tests pass, 1 otherwise
    """
    project_root = Path(__file__).parent.parent.parent
    print(f"📁 Project root: {project_root}")

    # Change to project root directory
    os.chdir(project_root)

    success = True

    # 1. Run unit tests
    print("\n🧪 Running unit tests...")
    if not run_command(
        ["uv", "run", "python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        "Unit tests",
    ):
        success = False

    # 2. Run tests with coverage
    print("\n📊 Running tests with coverage analysis...")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=unifiles",
            "--cov-report=term-missing",
        ],
        "Coverage analysis",
        critical=False,
    )

    # 3. Run integration tests (if they exist)
    integration_tests = project_root / "tests" / "integration"
    if integration_tests.exists() and any(integration_tests.glob("test_*.py")):
        print("\n🔗 Running integration tests...")
        if not run_command(
            ["uv", "run", "python", "-m", "pytest", str(integration_tests), "-v"],
            "Integration tests",
        ):
            success = False
    else:
        print("\n📝 Skipping integration tests (directory not found or no test files)")

    # 4. Generate HTML coverage report (optional)
    print("\n📈 Generating HTML coverage report...")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=unifiles",
            "--cov-report=html",
        ],
        "HTML coverage report",
        critical=False,
    )

    if success:
        print("\n🎉 All tests passed!")
        return 0
    print("\n💥 Some tests failed, please check and fix issues")
    return 1


if __name__ == "__main__":
    sys.exit(main())
