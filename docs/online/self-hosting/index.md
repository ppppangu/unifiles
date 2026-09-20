# 自部署

Unifiles Server 是独立的 `unifiles-server` Python 分发包。客户端始终通过 HTTP `/v1`
调用它，因此同一套 Python SDK、TypeScript SDK 和 CLI 可以在 SaaS 与本机服务间切换。

## 源码启动

```bash
git clone https://github.com/ppppangu/unifiles.git
cd unifiles
uv sync --all-packages --group dev

# Generate a random bootstrap key for this server.
export UNIFILES_BOOTSTRAP_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

UNIFILES_DATA_DIR=/var/lib/unifiles \
uv run unifiles-server --host 0.0.0.0 --port 8088
```

## Docker Compose

```bash
export UNIFILES_BOOTSTRAP_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d --build
curl http://localhost:8088/health
```

默认单机后端使用 SQLite 保存元数据、本地目录保存文件，适合单机自部署与开发环境。
原有 PostgreSQL 迁移脚本保留在 `apps/server/migrations/postgres/`，但当前版本不会自动执行。

## 客户端连接

```bash
printf '%s' "$UNIFILES_BOOTSTRAP_API_KEY" | unifiles config set local \
  --base-url http://localhost:8088 \
  --api-key-stdin
unifiles --profile local status
```
