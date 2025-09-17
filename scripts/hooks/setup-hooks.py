#!/usr/bin/env python3
"""
Git hooks setup script.
Sets up pre-commit and pre-push hooks for automated code quality checks.
"""

import os
import sys
from pathlib import Path


def create_git_hook(hook_name: str, script_content: str) -> bool:
    """
    Create a Git hook with the specified content.

    Args:
        hook_name: Name of the Git hook (e.g., 'pre-commit')
        script_content: Content of the hook script

    Returns:
        True if hook was created successfully, False otherwise
    """
    project_root = Path(__file__).parent.parent
    hooks_dir = project_root / ".git" / "hooks"

    if not hooks_dir.exists():
        print(
            "❌ Git hooks directory not found. Please run this script in a Git repository."
        )
        return False

    hook_path = hooks_dir / hook_name

    try:
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Make hook executable on Unix-like systems
        if os.name != "nt":  # Non-Windows systems
            os.chmod(hook_path, 0o755)

        print(f"✅ Created {hook_name} hook: {hook_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create {hook_name} hook: {e}")
        return False


def main() -> int:
    """
    Main function to set up Git hooks.

    Returns:
        0 if hooks were set up successfully, 1 otherwise
    """
    print("🔧 Setting up Git hooks...")

    project_root = Path(__file__).parent.parent

    # Pre-commit hook content
    pre_commit_content = f'''#!/bin/sh
# Pre-commit hook - Run code checks and formatting

echo "🚀 Running pre-commit checks..."
python "{project_root}/scripts/pre-commit.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "💥 Pre-commit checks failed, commit blocked"
    exit 1
fi

echo "✅ Pre-commit checks passed"
exit 0
'''

    # Pre-push hook content
    pre_push_content = f'''#!/bin/sh
# Pre-push hook - Run comprehensive validation

echo "🧪 Running pre-push validation..."
python "{project_root}/scripts/check/validate_all.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "💥 Validation failed, push blocked"
    exit 1
fi

echo "✅ All validations passed, safe to push"
exit 0
'''

    success = True

    # Create pre-commit hook
    if not create_git_hook("pre-commit", pre_commit_content):
        success = False

    # Create pre-push hook
    if not create_git_hook("pre-push", pre_push_content):
        success = False

    if success:
        print("\n🎉 Git hooks setup completed!")
        print("\n📝 Usage:")
        print(
            "  - pre-commit: Automatically runs code checks and formatting before each commit"
        )
        print(
            "  - pre-push: Automatically runs comprehensive validation before each push"
        )
        print("\n🔧 To bypass hooks when needed:")
        print("  - git commit --no-verify  (skip pre-commit)")
        print("  - git push --no-verify    (skip pre-push)")
        print("\n⚠️  Note: Only bypass hooks when absolutely necessary!")
        return 0
    print("\n💥 Git hooks setup failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
