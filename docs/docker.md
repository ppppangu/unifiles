# Docker Deployment

使用 Docker 和 Docker Compose 快速部署 Unifiles 及其所有依赖服务。

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+ (或 docker-compose 1.29+)

### 安装 Docker

#### Windows

下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

#### macOS

```bash
brew install --cask docker
```

或下载 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

#### Linux (Ubuntu)

```bash
# 添加 Docker 官方 GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加 Docker 仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/ppppangu/Unifiles.git
cd Unifiles
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少设置以下变量：

```bash
# 安全配置（必需）
SECURITY_SECRET_KEY=your-secret-key-at-least-32-characters-long

# 数据库密码
PG_PASSWORD=your_database_password

# MinIO 凭证
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123456
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4. 初始化数据库

```bash
# 执行数据库迁移
docker-compose exec api bash -c "
  for file in scripts/sql/*.sql; do
    psql -h postgres -U postgres -d unifiles -f \$file
  done
"
```

### 5. 验证部署

访问以下 URL：

- API 服务: http://localhost:8088
- API 文档: http://localhost:8088/docs
- MinIO 控制台: http://localhost:9001

## Docker Compose 配置

### docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: ankane/pgvector:latest
    container_name: unifiles-postgres
    environment:
      POSTGRES_DB: unifiles
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${PG_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis 缓存
  redis:
    image: redis:7-alpine
    container_name: unifiles-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MinIO 对象存储
  minio:
    image: minio/minio:latest
    container_name: unifiles-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # Unifiles API 服务
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: unifiles-api
    environment:
      # 数据库配置
      PG_HOST: postgres
      PG_PORT: 5432
      PG_DATABASE: unifiles
      PG_USER: postgres
      PG_PASSWORD: ${PG_PASSWORD:-postgres}

      # Redis 配置
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0

      # MinIO 配置
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      MINIO_USE_SSL: "false"

      # 应用配置
      APP_ENV: production
      APP_DEBUG: "false"
      SECURITY_SECRET_KEY: ${SECURITY_SECRET_KEY}
    ports:
      - "8088:8088"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  # Upload Worker
  upload-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    container_name: unifiles-upload-worker
    command: python -m unifiles.workers.upload_worker
    environment:
      # 同 API 配置
      PG_HOST: postgres
      PG_PORT: 5432
      PG_DATABASE: unifiles
      PG_USER: postgres
      PG_PASSWORD: ${PG_PASSWORD:-postgres}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      MINIO_USE_SSL: "false"
      SECURITY_SECRET_KEY: ${SECURITY_SECRET_KEY}
    depends_on:
      - api
    restart: unless-stopped

  # Extraction Worker
  extraction-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    container_name: unifiles-extraction-worker
    command: python -m unifiles.workers.extraction_worker
    environment:
      # 同 API 配置
      PG_HOST: postgres
      PG_PORT: 5432
      PG_DATABASE: unifiles
      PG_USER: postgres
      PG_PASSWORD: ${PG_PASSWORD:-postgres}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      MINIO_USE_SSL: "false"
      SECURITY_SECRET_KEY: ${SECURITY_SECRET_KEY}
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:

networks:
  default:
    name: unifiles-network
```

## Dockerfile

### API Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY unifiles ./unifiles
COPY scripts ./scripts

# 安装 Python 依赖
RUN uv sync --frozen

# 暴露端口
EXPOSE 8088

# 启动命令
CMD ["uv", "run", "uvicorn", "unifiles.server.main:app", "--host", "0.0.0.0", "--port", "8088"]
```

### Worker Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY unifiles ./unifiles
COPY scripts ./scripts

RUN uv sync --frozen

CMD ["python", "-m", "unifiles.workers.upload_worker"]
```

## 常用命令

### 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 启动特定服务
docker-compose up -d api

# 停止所有服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器和数据卷
docker-compose down -v

# 重启服务
docker-compose restart

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service_name]
```

### 数据库管理

```bash
# 进入数据库容器
docker-compose exec postgres psql -U postgres -d unifiles

# 备份数据库
docker-compose exec postgres pg_dump -U postgres unifiles > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U postgres unifiles < backup.sql

# 执行 SQL 脚本
docker-compose exec postgres psql -U postgres -d unifiles -f /path/to/script.sql
```

### 应用管理

```bash
# 进入 API 容器
docker-compose exec api bash

# 查看 API 日志
docker-compose logs -f api

# 重启 Worker
docker-compose restart upload-worker extraction-worker

# 扩展 Worker 数量
docker-compose up -d --scale extraction-worker=3
```

## 生产环境优化

### 1. 使用预构建镜像

```yaml
services:
  api:
    image: unifiles/api:latest  # 使用预构建镜像
    # build: ...  # 注释掉 build 配置
```

### 2. 资源限制

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 3. 日志管理

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. 健康检查

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 5. 持久化存储

使用命名卷而不是绑定挂载：

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/postgres
```

## 监控和日志

### Prometheus + Grafana

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### 日志聚合 (ELK Stack)

```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## 故障排查

### 容器无法启动

```bash
# 查看容器日志
docker-compose logs api

# 检查容器状态
docker-compose ps

# 进入容器调试
docker-compose exec api bash
```

### 数据库连接失败

```bash
# 测试数据库连接
docker-compose exec api python -c "
from unifiles.core.database.pool_manager import get_pool_manager
import asyncio
async def test():
    pm = await get_pool_manager()
    await pm.initialize()
    print('Database connected!')
asyncio.run(test())
"
```

### MinIO 访问问题

```bash
# 测试 MinIO 连接
docker-compose exec api python -c "
from minio import Minio
client = Minio('minio:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)
print(client.list_buckets())
"
```

## 安全加固

### 1. 使用 Secrets

```yaml
services:
  api:
    secrets:
      - db_password
      - secret_key

secrets:
  db_password:
    file: ./secrets/db_password.txt
  secret_key:
    file: ./secrets/secret_key.txt
```

### 2. 网络隔离

```yaml
networks:
  frontend:
  backend:

services:
  api:
    networks:
      - frontend
      - backend

  postgres:
    networks:
      - backend  # 不暴露到前端网络
```

### 3. 非 root 用户运行

```dockerfile
RUN useradd -m -u 1000 unifiles
USER unifiles
```

## 相关文档

- [部署指南](deployment.md) - 传统部署方式
- [CI/CD 配置](deployment.md) - 自动化部署
- [监控配置](configuration.md) - 监控告警设置

## 下一步

- [配置管理](configuration.md) - 详细配置说明
- [性能优化](../ARCHITECTURE.md) - 优化指南
- [故障排查](troubleshooting.md) - 常见问题解决
