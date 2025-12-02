# Docker Compose 部署

本指南介绍如何使用 Docker Compose 在单机上部署 Unifiles。

## 概述

Docker Compose 部署适合:
- 开发和测试环境
- 小规模生产环境 (< 10 并发用户)
- 概念验证和演示

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-org/unifiles.git
cd unifiles
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
vim .env
```

关键配置项:

```bash
# .env

# === 数据库 ===
PG_HOST=postgres
PG_PORT=5432
PG_DATABASE=unifiles
PG_USER=unifiles
PG_PASSWORD=your_secure_password_here

# === Redis ===
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here

# === MinIO ===
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=unifiles_access_key
MINIO_SECRET_KEY=your_minio_secret_key_here
MINIO_SECURE=false

# === 安全 ===
SECURITY_SECRET_KEY=your_secret_key_at_least_32_characters_long

# === 应用 ===
API_HOST=0.0.0.0
API_PORT=8088
DEBUG=false
LOG_LEVEL=INFO
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4. 初始化数据库

```bash
# 运行迁移
docker-compose exec api python -m unifiles.scripts.migrate

# 创建初始管理员
docker-compose exec api python -m unifiles.scripts.create_admin \
  --email admin@example.com \
  --password your_admin_password
```

### 5. 验证部署

```bash
# 健康检查
curl http://localhost:8088/health

# 应返回
# {"status": "healthy", "version": "x.x.x"}
```

## docker-compose.yml 详解

### 完整配置文件

```yaml
# docker-compose.yml
version: '3.8'

services:
  # === API 服务 ===
  api:
    build:
      context: .
      dockerfile: Dockerfile
    image: unifiles/api:latest
    ports:
      - "${API_PORT:-8088}:8088"
    environment:
      - PG_HOST=postgres
      - PG_PORT=5432
      - PG_DATABASE=${PG_DATABASE}
      - PG_USER=${PG_USER}
      - PG_PASSWORD=${PG_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - SECURITY_SECRET_KEY=${SECURITY_SECRET_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # === 后台 Worker ===
  worker-upload:
    build:
      context: .
      dockerfile: Dockerfile
    image: unifiles/api:latest
    command: python -m unifiles.workers.upload_worker
    environment:
      - PG_HOST=postgres
      - PG_PORT=5432
      - PG_DATABASE=${PG_DATABASE}
      - PG_USER=${PG_USER}
      - PG_PASSWORD=${PG_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
    depends_on:
      - api
    restart: unless-stopped

  worker-extraction:
    build:
      context: .
      dockerfile: Dockerfile
    image: unifiles/api:latest
    command: python -m unifiles.workers.extraction_worker
    environment:
      - PG_HOST=postgres
      - PG_PORT=5432
      - PG_DATABASE=${PG_DATABASE}
      - PG_USER=${PG_USER}
      - PG_PASSWORD=${PG_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
    depends_on:
      - api
    restart: unless-stopped

  # === PostgreSQL (with pgvector) ===
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=${PG_DATABASE}
      - POSTGRES_USER=${PG_USER}
      - POSTGRES_PASSWORD=${PG_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/sql:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER} -d ${PG_DATABASE}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # === Redis ===
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # === MinIO ===
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${MINIO_ACCESS_KEY}
      - MINIO_ROOT_PASSWORD=${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # === Nginx 反向代理 (可选) ===
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### Nginx 配置

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8088;
    }

    # HTTP -> HTTPS 重定向
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # HTTPS 服务
    server {
        listen 443 ssl http2;
        server_name _;

        ssl_certificate /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;

        # 文件上传大小限制
        client_max_body_size 100M;

        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket 支持 (如需要)
        location /ws {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

## 生产环境配置

### 资源限制

```yaml
# docker-compose.prod.yml
version: '3.8'

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

  postgres:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 8G
        reservations:
          cpus: '1'
          memory: 4G

  redis:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G

  minio:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

使用生产配置:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 多副本部署

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  api:
    deploy:
      replicas: 3

  worker-upload:
    deploy:
      replicas: 2

  worker-extraction:
    deploy:
      replicas: 2
```

使用 Docker Swarm:

```bash
docker swarm init
docker stack deploy -c docker-compose.yml -c docker-compose.scale.yml unifiles
```

## 常用操作

### 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启特定服务
docker-compose restart api

# 查看服务日志
docker-compose logs -f api

# 进入容器
docker-compose exec api bash
```

### 数据备份

```bash
# 备份 PostgreSQL
docker-compose exec postgres pg_dump -U unifiles unifiles > backup.sql

# 备份 Redis
docker-compose exec redis redis-cli -a ${REDIS_PASSWORD} BGSAVE

# 备份 MinIO 数据卷
docker run --rm -v unifiles_minio_data:/data -v $(pwd):/backup \
  alpine tar cvf /backup/minio_backup.tar /data
```

### 更新版本

```bash
# 拉取最新镜像
docker-compose pull

# 重启服务 (零停机)
docker-compose up -d --no-deps --build api
docker-compose up -d --no-deps --build worker-upload
docker-compose up -d --no-deps --build worker-extraction
```

### 查看资源使用

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
docker system df

# 清理未使用资源
docker system prune -a
```

## 故障排除

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs --tail=100 api

# 检查健康状态
docker-compose ps

# 验证配置
docker-compose config
```

### 数据库连接失败

```bash
# 测试数据库连接
docker-compose exec api python -c "
import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect(
        host='postgres',
        database='unifiles',
        user='unifiles',
        password='your_password'
    )
    print(await conn.fetchval('SELECT version()'))
    await conn.close()

asyncio.run(test())
"
```

### 存储问题

```bash
# 检查 MinIO 状态
docker-compose exec minio mc admin info local

# 检查存储桶
docker-compose exec minio mc ls local

# 检查磁盘空间
df -h
```

## 下一步

- [配置说明](./configuration.md) - 详细配置选项
- [可观测性](./observability.md) - 添加监控
- [备份与恢复](./backup-restore.md) - 数据保护
