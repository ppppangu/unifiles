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
uv run ruff check apps packages/python scripts codegen/scripts
uv run mypy packages/python/src apps/server/src scripts codegen/scripts
uv run pytest

# TypeScript SDK 与 CLI
npm run check

# 协议与文档
uv run python codegen/scripts/codegen.py validate
uv run python codegen/scripts/codegen.py check all
uv run mkdocs build --strict
```

## 修改 API

`contracts/openapi/unifiles.yaml` 是唯一协议源。先修改契约，再重新生成 FastAPI 协议层和两个 SDK core：

```bash
npm run generate
```

CI 会重新生成三套代码并检查 diff。生成目录可以整体替换；手写 feature modules、业务服务和 SDK
扩展层位于生成目录之外，不会被覆盖。Python/TypeScript 的 URL、参数和 wire 序列化由生成
core 负责，手写 facade 只补充 `wait()`、重试和异常映射等协议之外的体验。

## 本机 CLI profile

```bash
printf '%s' sk_test_local | node apps/cli/dist/index.js config set local \
  --base-url http://localhost:8088 \
  --api-key-stdin
node apps/cli/dist/index.js --profile local status
```

## 下一步

- [自部署指南](../self-hosting/index.md)
- [API 参考](../api-reference/index.md)
