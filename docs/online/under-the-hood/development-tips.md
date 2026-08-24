# 开发技巧

## 环境

- Python 3.11+
- Node.js 22+
- uv
- npm

```bash
git clone https://github.com/ppppangu/unifiles.git
cd unifiles
uv sync --all-packages --group dev --group docs
npm ci
```

## 启动 Server

```bash
UNIFILES_BOOTSTRAP_API_KEY=sk_test_local \
UNIFILES_DATA_DIR=.unifiles-data \
uv run unifiles-server --reload --port 8088
```

Swagger UI 位于 `http://localhost:8088/docs`。SQLite 单机后端会在启动时恢复未完成的
Extraction 与 Document 任务。

## 验证

```bash
# Python Server 与 SDK
uv run ruff check apps packages/python scripts
uv run mypy packages/python/src apps/server/src --exclude _generated
uv run pytest

# TypeScript SDK 与 CLI
npm run check

# 协议与文档
uv run python scripts/check_openapi.py
uv run mkdocs build --strict
```

## 修改 API

FastAPI `/v1` 路由与 `api/openapi.yaml` 必须同步。修改路由后执行：

```bash
uv run python scripts/export_openapi.py
uv run python scripts/generate_contract.py
```

CI 会重新生成 Python/TypeScript wire types 并检查 diff。公开 SDK facade 保持手写，以便
Python 使用 snake_case、TypeScript 使用 camelCase。

## 本机 CLI profile

```bash
printf '%s' sk_test_local | node packages/cli/dist/index.js config set local \
  --base-url http://localhost:8088 \
  --api-key-stdin
node packages/cli/dist/index.js --profile local status
```

## 下一步

- [自部署指南](../self-hosting/index.md)
- [API 参考](../api-reference/index.md)
