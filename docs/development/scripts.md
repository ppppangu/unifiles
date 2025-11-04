# Scripts Directory

这个目录包含用于代码质量保证、格式化和自动化检查的脚本。

## 脚本列表

### 🎨 代码格式化
- **`format.py`** - 使用 ruff 和 black 格式化 Python 代码
  ```bash
  python scripts/format.py
  ```

### 🔍 代码检查  
- **`lint.py`** - 运行代码质量检查（ruff、mypy、bandit、isort）
  ```bash
  python scripts/lint.py
  ```

### 🧪 测试运行
- **`test.py`** - 运行所有测试并生成覆盖率报告
  ```bash
  python scripts/test.py
  ```

### 🚀 Pre-commit 检查
- **`pre-commit.py`** - 提交前运行的检查脚本
  ```bash
  python scripts/pre-commit.py
  ```

### 🔧 Git 钩子设置
- **`setup-hooks.py`** - 自动设置 Git pre-commit 和 pre-push 钩子
  ```bash
  python scripts/setup-hooks.py
  ```

## 快速开始

1. **设置 Git 钩子** (推荐):
   ```bash
   python scripts/setup-hooks.py
   ```

2. **手动运行代码检查和格式化**:
   ```bash
   # 格式化代码
   python scripts/format.py
   
   # 检查代码质量
   python scripts/lint.py
   
   # 运行测试
   python scripts/test.py
   ```

## 工具依赖

确保安装了以下工具:
```bash
pip install ruff black isort mypy bandit pytest pytest-cov
```

## Git 钩子说明

- **pre-commit**: 每次 `git commit` 前自动运行代码格式化和检查
- **pre-push**: 每次 `git push` 前自动运行测试

如需跳过钩子检查:
```bash
git commit --no-verify  # 跳过 pre-commit
git push --no-verify    # 跳过 pre-push
```