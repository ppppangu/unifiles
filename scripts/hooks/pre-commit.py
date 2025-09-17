#!/usr/bin/env python3
"""
Pre-commit hook script.
Runs code checks and formatting before commits.
"""

import subprocess
import sys
from pathlib import Path
from typing import List


def run_script(script_path: Path) -> bool:
    """
    Run a script and return success status.

    Args:
        script_path: Path to the script to run

    Returns:
        True if script succeeded, False otherwise
    """
    try:
        result = subprocess.run([sys.executable, str(script_path)], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False


def get_staged_python_files() -> List[str]:
    """
    Get Python files currently staged for commit.

    Returns:
        List of staged Python file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        python_files = [f for f in files if f.endswith(".py") and f]
        return python_files
    except subprocess.CalledProcessError:
        return []


def main() -> int:
    """
    Main function for pre-commit checks.

    Returns:
        0 if all checks pass, 1 otherwise
    """
    print("🚀 Running pre-commit checks...")

    # Get staged Python files
    staged_files = get_staged_python_files()

    if not staged_files:
        print("📝 No Python files staged, skipping checks")
        return 0

    print(f"📁 Checking {len(staged_files)} Python files:")
    for file in staged_files:
        print(f"  - {file}")

    success = True
    scripts_dir = Path(__file__).parent

    # 1. Run code formatting
    print("\n🎨 Running code formatting...")
    format_script = scripts_dir.parent / "dev" / "format.py"
    if not run_script(format_script):
        print("❌ Code formatting failed")
        success = False

    # 2. Run code linting
    print("\n🔍 Running code linting...")
    lint_script = scripts_dir.parent / "check" / "lint.py"
    if not run_script(lint_script):
        print("❌ Code linting failed")
        success = False

    # 3. Re-add formatted files to staging area
    if success:
        print("\n📝 Re-adding formatted files to staging area...")
        try:
            for file in staged_files:
                subprocess.run(["git", "add", file], check=True)
            print("✅ Files re-added to staging area")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to add files to staging area: {e}")
            success = False

    if success:
        print("\n🎉 Pre-commit checks passed, ready to commit!")
        return 0
    print("\n💥 Pre-commit checks failed, please fix issues and try again")
    return 1


if __name__ == "__main__":
    sys.exit(main())
