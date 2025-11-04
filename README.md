Unifiles
========

简洁、可扩展的文件处理与知识库服务。提供上传、解析、抽取、分块、入库与检索等能力，并内建观测与统一日志。

快速开始
--
- Python 3.11+
- 推荐使用 `uv` 包管理器（也可用 `pip`）

安装依赖：
- 使用 uv：`uv sync`
- 使用 pip：`pip install -e .`（可选）

运行服务：
- `uv run python -m Unifiles.app.main`

开发常用命令
--
- 代码格式化：`uv run python scripts/dev/format.py`
- 清理缓存与构建产物：
  - 预览：`python scripts/dev/clean.py`
  - 执行：`python scripts/dev/clean.py --apply`
  - 包含 .venv 等重项：`python scripts/dev/clean.py --apply --all`

目录结构
--
- `Unifiles/` 核心代码（app、core、services、storage、types 等）
- `tests/` 单测与集成测试
- `scripts/` 开发与运维脚本
- `docs/` 文档（见下）

文档索引（精简）
--
- 入门：`docs/QUICK_START.md`（若损坏，请先参考本 README 的“快速开始”）
- API：`docs/API_REFERENCE.md` 或 `docs/api/openapi.yaml`
- 架构：`docs/ARCHITECTURE.md`（若损坏，参考 `Unifiles/core` 目录结构）
- 开发：`docs/DEVELOPMENT.md`

注意事项
--
- 仓库中存在部分历史/生成文件（如 `*.egg-info/`、日志、`__pycache__`、`.pytest_cache` 等），可使用上方清理脚本统一清理。
- 如发现脚本/文档乱码（编码损坏），建议逐步替换为 UTF-8 并简化内容，保持单一来源文档（以 Markdown 为主）。

