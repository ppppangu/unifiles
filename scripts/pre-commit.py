#!/usr/bin/env python3
"""
Pre-commit 钩子脚本
在提交前运行代码检查和格式化
"""

import subprocess
import sys
from pathlib import Path


def run_script(script_name: str) -> bool:
    """运行指定的脚本"""
    script_path = Path(__file__).parent / script_name
    try:
        result = subprocess.run([sys.executable, str(script_path)], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False


def get_staged_python_files() -> list[str]:
    """获取暂存区中的 Python 文件"""
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


def main():
    """主函数"""
    print("🚀 运行 pre-commit 检查...")

    # 获取暂存的 Python 文件
    staged_files = get_staged_python_files()

    if not staged_files:
        print("📝 没有 Python 文件被暂存，跳过检查")
        return 0

    print(f"📁 检查 {len(staged_files)} 个 Python 文件:")
    for file in staged_files:
        print(f"  - {file}")

    success = True

    # 1. 运行格式化
    print("\n🎨 运行代码格式化...")
    if not run_script("format.py"):
        print("❌ 代码格式化失败")
        success = False

    # 2. 运行代码检查
    print("\n🔍 运行代码检查...")
    if not run_script("lint.py"):
        print("❌ 代码检查失败")
        success = False

    # 3. 重新添加格式化后的文件到暂存区
    if success:
        print("\n📝 重新添加格式化后的文件到暂存区...")
        try:
            for file in staged_files:
                subprocess.run(["git", "add", file], check=True)
            print("✅ 文件已重新添加到暂存区")
        except subprocess.CalledProcessError as e:
            print(f"❌ 添加文件到暂存区失败: {e}")
            success = False

    if success:
        print("\n🎉 Pre-commit 检查通过，可以提交！")
        return 0
    else:
        print("\n💥 Pre-commit 检查失败，请修复问题后重新提交")
        return 1


if __name__ == "__main__":
    sys.exit(main())
