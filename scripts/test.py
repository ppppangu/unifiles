#!/usr/bin/env python3
"""
测试运行脚本
运行项目的所有测试
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

    # 1. 运行单元测试
    print("\n🧪 运行单元测试...")
    test_commands = [
        ["uv", "run", "python", "-m", "pytest", "tests/", "-v", "--tb=short"],
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
    ]

    for cmd in test_commands:
        if not run_command(cmd, f"运行测试: {' '.join(cmd[2:])}"):
            print("⚠️  测试命令失败，尝试下一个...")
            success = False

    # 2. 运行集成测试（如果存在）
    integration_tests = project_root / "tests" / "integration"
    if integration_tests.exists() and any(integration_tests.glob("test_*.py")):
        print("\n🔗 运行集成测试...")
        if not run_command(
            ["uv", "run", "python", "-m", "pytest", str(integration_tests), "-v"],
            "集成测试",
        ):
            success = False
    else:
        print("\n📝 跳过集成测试（目录不存在或无测试文件）")

    # 3. 检查测试覆盖率
    print("\n📊 生成覆盖率报告...")
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
        "覆盖率报告",
    )

    if success:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n💥 测试失败，请检查并修复问题")
        return 1


if __name__ == "__main__":
    sys.exit(main())
