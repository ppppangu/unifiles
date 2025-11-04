# Deployment

Unifiles 支持多种部署方式，包括 Docker、Kubernetes、传统虚拟机等。本节将指导您完成生产环境的部署配置。

## 部署方式

### Docker 部署（推荐）
使用 Docker 和 Docker Compose 快速部署完整的 Unifiles 栈。

[Docker 部署指南](docker.md)

### Kubernetes 部署
使用 Kubernetes 部署高可用、可扩展的 Unifiles 集群。

[K8s 部署指南（待补充）]

### 传统部署
在虚拟机或物理机上部署 Unifiles。

[传统部署指南](deployment.md)

## 环境要求

### 硬件要求

**最小配置（开发/测试）**:
- CPU: 2 核
- 内存: 4GB
- 存储: 50GB

**推荐配置（生产环境）**:
- CPU: 4 核+
- 内存: 8GB+
- 存储: 200GB+ (根据文件存储需求调整)

### 软件要求

- **Python**: 3.11+
- **PostgreSQL**: 15+ (with pgvector extension)
- **Redis**: 7+
- **MinIO**: Latest stable
- **Docker**: 20.10+ (if using Docker)

## 依赖服务

### PostgreSQL

```bash
# 安装 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### MinIO

```bash
# 启动 MinIO
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"
```

### Redis

```bash
# 启动 Redis
docker run -d \
  -p 6379:6379 \
  redis:7-alpine
```

## 环境变量配置

### 必需环境变量

```bash
# 数据库配置
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=unifiles
PG_USER=postgres
PG_PASSWORD=your_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_USE_SSL=false

# 安全配置（必需，至少32字符）
SECURITY_SECRET_KEY=your-secret-key-at-least-32-chars
```

### 可选环境变量

```bash
# 应用配置
APP_ENV=production
APP_DEBUG=false
APP_LOG_LEVEL=INFO

# OpenTelemetry（可观测性）
OTEL_ENABLED=false
OTEL_EXPORTER_ENDPOINT=localhost:4317

# 性能配置
MAX_UPLOAD_SIZE=100MB
WORKER_CONCURRENCY=4
```

[完整配置说明](configuration.md)

## 数据库初始化

```bash
# 1. 创建数据库
createdb -U postgres unifiles

# 2. 运行迁移脚本
psql -U postgres -d unifiles -f scripts/sql/011-create-extensions.sql
psql -U postgres -d unifiles -f scripts/sql/021-create-users.sql
psql -U postgres -d unifiles -f scripts/sql/031-create-file-management.sql
# ... 依次执行其他迁移脚本
```

[数据库迁移指南（待补充）]

## 启动应用

### 开发模式

```bash
# 安装依赖
uv sync

# 启动 API 服务
uv run uvicorn unifiles.app.main:app --host 0.0.0.0 --port 8088 --reload

# 启动 Worker（另一个终端）
uv run python -m unifiles.workers.upload_worker
uv run python -m unifiles.workers.extraction_worker
```

### 生产模式

```bash
# 使用 Gunicorn + Uvicorn Workers
gunicorn unifiles.app.main:app \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --log-level info \
  --access-logfile - \
  --error-logfile -
```

## 健康检查

```bash
# 检查 API 服务
curl http://localhost:8088/health

# 预期响应
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "ok",
    "redis": "ok",
    "minio": "ok"
  }
}
```

## 负载均衡

### Nginx 配置示例

```nginx
upstream unifiles_backend {
    server 127.0.0.1:8088;
    server 127.0.0.1:8089;
    server 127.0.0.1:8090;
}

server {
    listen 80;
    server_name unifiles.example.com;

    location / {
        proxy_pass http://unifiles_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 大文件上传
        client_max_body_size 100M;
    }
}
```

## 监控与告警

### Prometheus 配置

```yaml
scrape_configs:
  - job_name: 'unifiles'
    static_configs:
      - targets: ['localhost:8088']
    metrics_path: '/metrics'
```

[监控配置详细说明](../observability/monitoring.md)

## CI/CD

Unifiles 支持多种 CI/CD 工具，包括 GitHub Actions、GitLab CI、Jenkins 等。

[CI/CD 配置指南](cicd.md)

## 故障排查

[故障排查指南（待补充）]

## 安全加固

[安全加固指南（待补充）]

## 备份与恢复

[备份恢复指南（待补充）]

## 下一步

- [Docker 部署](docker.md) - 使用 Docker 快速部署
- [CI/CD 设置](cicd.md) - 自动化部署流程
- [配置管理](configuration.md) - 详细的配置选项
- [可观测性](../observability/index.md) - 监控和日志配置
