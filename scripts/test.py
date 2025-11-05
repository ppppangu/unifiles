#!/usr/bin/env python3
"""
Test runner entry point.
This script delegates to the actual test runner in scripts/check/test.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run the main test script."""
    script_dir = Path(__file__).parent
    test_script = script_dir / "check" / "test.py"

    # Run the actual test script
    result = subprocess.run([sys.executable, str(test_script)], cwd=script_dir.parent)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
