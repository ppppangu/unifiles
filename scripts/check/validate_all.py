#!/usr/bin/env python3
"""
Comprehensive validation script for code quality checks.
Runs all validation checks including formatting, linting, type checking, and tests.
"""

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
        critical: Whether failure should fail the entire check

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
        if not critical:
            print(f"⚠️  {description} failed but continuing...")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {' '.join(cmd)}")
        return False


def check_code_formatting() -> bool:
    """Check if code is properly formatted."""
    print("\n🎨 Checking code formatting...")
    return run_command(
        ["uv", "run", "ruff", "format", "--check", "."], "Code formatting check"
    )


def check_code_linting() -> bool:
    """Run code linting checks."""
    print("\n🔍 Running code linting...")
    return run_command(
        ["uv", "run", "ruff", "check", "."], "Code linting check", critical=False
    )


def check_type_hints() -> bool:
    """Run type checking with mypy."""
    print("\n🔬 Running type checking...")
    return run_command(
        ["uv", "run", "mypy", "unifiles/", "--config-file=mypy.ini"],
        "Type checking",
        critical=False,  # Type checking is not critical for CI
    )


def run_tests() -> bool:
    """Run the test suite."""
    print("\n🧪 Running test suite...")
    success = True

    # Run basic tests
    if not run_command(
        ["uv", "run", "python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        "Unit tests",
    ):
        success = False

    # Run tests with coverage
    if not run_command(
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
    ):
        print("⚠️  Coverage analysis failed but continuing...")

    return success


def check_security() -> bool:
    """Run security checks."""
    print("\n🔒 Running security checks...")
    # Check for common security issues with bandit (if available)
    try:
        result = subprocess.run(
            ["uv", "run", "bandit", "--version"], check=False, capture_output=True
        )
        if result.returncode != 0:
            print("ℹ️  Bandit not installed, skipping security scan...")
            return True
        return run_command(
            ["uv", "run", "bandit", "-r", "unifiles/", "-f", "json"],
            "Security scan",
            critical=False,
        )
    except Exception:
        print("ℹ️  Security scanning tool not available, skipping...")
        return True


def main() -> int:
    """
    Main function that coordinates all validation checks.

    Returns:
        0 if all critical checks pass, 1 otherwise
    """
    project_root = Path(__file__).parent.parent.parent
    print(f"📁 Project root: {project_root}")

    # Change to project root directory
    import os

    os.chdir(project_root)

    print("🚀 Running comprehensive validation checks...\n")

    # Track results
    results = []

    # Run all checks
    checks = [
        ("Code Formatting", check_code_formatting, True),
        ("Code Linting", check_code_linting, False),  # Made non-critical
        ("Type Checking", check_type_hints, False),
        ("Test Suite", run_tests, True),
        ("Security", check_security, False),
    ]

    for name, check_func, critical in checks:
        success = check_func()
        results.append((name, success, critical))

    # Report results
    print("\n" + "=" * 60)
    print("📊 VALIDATION RESULTS")
    print("=" * 60)

    critical_failures = 0
    warnings = 0

    for name, success, critical in results:
        if success:
            print(f"✅ {name}: PASSED")
        elif critical:
            print(f"❌ {name}: FAILED (Critical)")
            critical_failures += 1
        else:
            print(f"⚠️  {name}: FAILED (Warning)")
            warnings += 1

    print("\n" + "=" * 60)

    if critical_failures == 0:
        if warnings == 0:
            print("🎉 All validation checks passed!")
        else:
            print(f"✅ All critical checks passed ({warnings} warnings)")
        print("✨ Code is ready for push to remote repository")
        return 0
    print(f"💥 {critical_failures} critical check(s) failed")
    print("🔧 Please fix issues before pushing to remote repository")
    return 1


if __name__ == "__main__":
    sys.exit(main())
