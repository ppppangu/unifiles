#!/usr/bin/env python3
"""
代码格式化脚本
使用 ruff 对 Python 代码进行格式化
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
        print(f"✅ {description} 完成")
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

    # 1. 使用 ruff 检查和修复
    print("\n🔍 使用 ruff 进行代码检查和自动修复...")
    if not run_command(["uv", "run", "ruff", "check", ".", "--fix"], "Ruff 自动修复"):
        success = False

    if not run_command(["uv", "run", "ruff", "format", "."], "Ruff 格式化"):
        success = False

    if success:
        print("\n🎉 代码格式化完成！")
        return 0
    else:
        print("\n💥 代码格式化过程中出现错误")
        return 1


if __name__ == "__main__":
    sys.exit(main())
