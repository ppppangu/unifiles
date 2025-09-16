#!/usr/bin/env python3
"""
Git 钩子设置脚本
设置 pre-commit 和 pre-push 钩子
"""

import os
import sys
from pathlib import Path


def create_git_hook(hook_name: str, script_content: str) -> bool:
    """创建 Git 钩子"""
    project_root = Path(__file__).parent.parent
    hooks_dir = project_root / ".git" / "hooks"

    if not hooks_dir.exists():
        print("❌ Git hooks 目录不存在，请确保在 Git 仓库中运行此脚本")
        return False

    hook_path = hooks_dir / hook_name

    try:
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # 使钩子可执行
        if os.name != "nt":  # 非 Windows 系统
            os.chmod(hook_path, 0o755)

        print(f"✅ 创建 {hook_name} 钩子: {hook_path}")
        return True
    except Exception as e:
        print(f"❌ 创建 {hook_name} 钩子失败: {e}")
        return False


def main():
    """主函数"""
    print("🔧 设置 Git 钩子...")

    project_root = Path(__file__).parent.parent

    # Pre-commit 钩子内容
    pre_commit_content = f'''#!/bin/sh
# Pre-commit hook - 运行代码检查和格式化

echo "🚀 运行 pre-commit 检查..."
python "{project_root}/scripts/pre-commit.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "💥 Pre-commit 检查失败，提交被阻止"
    exit 1
fi

echo "✅ Pre-commit 检查通过"
exit 0
'''

    # Pre-push 钩子内容
    pre_push_content = f'''#!/bin/sh
# Pre-push hook - 运行测试

echo "🧪 运行测试..."
python "{project_root}/scripts/test.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "💥 测试失败，推送被阻止"
    exit 1
fi

echo "✅ 测试通过，可以推送"
exit 0
'''

    success = True

    # 创建 pre-commit 钩子
    if not create_git_hook("pre-commit", pre_commit_content):
        success = False

    # 创建 pre-push 钩子
    if not create_git_hook("pre-push", pre_push_content):
        success = False

    if success:
        print("\n🎉 Git 钩子设置完成！")
        print("\n📝 使用说明:")
        print("  - pre-commit: 每次提交前自动运行代码检查和格式化")
        print("  - pre-push: 每次推送前自动运行测试")
        print("\n🔧 如需禁用钩子，可以使用:")
        print("  - git commit --no-verify  (跳过 pre-commit)")
        print("  - git push --no-verify    (跳过 pre-push)")
        return 0
    else:
        print("\n💥 Git 钩子设置失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
