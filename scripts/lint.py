#!/usr/bin/env python3
"""
代码检查脚本
使用 ruff、isort、mypy 进行代码质量检查
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """运行命令并返回成功状态"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} 通过")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败:")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"❌ 命令未找到: {' '.join(cmd)}")
        return False


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    print(f"📁 项目根目录: {project_root}")

    # 切换到项目根目录
    import os

    os.chdir(project_root)

    success = True

    # 1. Ruff 代码检查
    print("\n🔍 运行 ruff 代码检查...")
    if not run_command(["uv", "run", "ruff", "check", "."], "Ruff 代码检查"):
        success = False

    # 2. Ruff 格式检查
    print("\n🎨 检查代码格式...")
    if not run_command(
        ["uv", "run", "ruff", "format", "--check", "."], "Ruff 格式检查"
    ):
        success = False

    # 3. MyPy 类型检查（宽松模式）
    print("\n🔬 运行 MyPy 类型检查...")
    if not run_command(
        ["uv", "run", "mypy", "unifiles/", "--config-file=mypy.ini"], "MyPy 类型检查"
    ):
        print("⚠️  MyPy 类型检查失败，但继续执行...")

    if success:
        print("\n🎉 所有代码检查通过！")
        return 0
    else:
        print("\n💥 代码检查发现问题，请修复后再提交")
        return 1


if __name__ == "__main__":
    sys.exit(main())
