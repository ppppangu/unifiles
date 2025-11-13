# Unifiles 部署指南

## 目录

- [Linux 服务器部署](#linux-服务器部署)
- [本地部署](#本地部署)
- [环境配置](#环境配置)
- [启动服务](#启动服务)

---

## Linux 服务器部署

### 1. PostgreSQL 数据库部署

#### 使用 Supabase PostgreSQL 官方镜像

##### 生产环境优化版本

```bash
docker run -d \
  --name supabase-postgres-prod \
  --restart unless-stopped \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=unifiles_db \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -p 5432:5432 \
  -v supabase-postgres-data:/var/lib/postgresql/data \
  -v supabase-postgres-config:/etc/postgresql \
  --cpus=4 \
  --memory=8g \
  --memory-swap=4g \
  --health-cmd="pg_isready -U postgres" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  supabase/postgres:latest
```

##### 验证部署

```bash
# 检查容器状态
docker ps | grep supabase-postgres

# 查看容器日志
docker logs supabase-postgres

# 测试数据库连接
docker exec -it supabase-postgres psql -U postgres -c "SELECT version();"
```

##### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| POSTGRES_USER | 数据库超级用户 | postgres |
| POSTGRES_PASSWORD | 用户密码 | **必须设置** |
| POSTGRES_DB | 默认数据库 | postgres |
| PGDATA | 数据目录 | /var/lib/postgresql/data/pgdata |

##### 数据持久化

- `supabase-postgres-data`: PostgreSQL 数据文件持久化
- `supabase-postgres-config`: 配置文件持久化（可选）

##### 网络和端口

- **默认端口**: 5432
- **安全建议**: 
  - 确保防火墙开放对应端口
  - 生产环境建议使用反向代理和 SSL 证书

### 2. RabbitMQ 消息队列部署

```bash
docker run -d \
  --name rabbitmq \
  --restart unless-stopped \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \
  -e RABBITMQ_DEFAULT_VHOST=/ \
  -v /unifiles/rabbitmq/data:/var/lib/rabbitmq \
  -v /unifiles/rabbitmq/conf/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:4-management
```

#### 检查 RabbitMQ 部署状态

```bash
docker logs rabbitmq
```

### 3. 附加服务部署

#### Convert2PDF 服务

> [Convert2PDF 服务部署指南](https://github.com/ppppangu/convert2pdf_server)

#### AI 模型服务

需要自行部署以下服务：

- **Embedding 服务**: bge-m3 模型可用
- **VL 模型服务**: Qwen3-8B-VL 模型可用

---

## 本地部署

### 1. 获取源代码

```bash
# 克隆项目
git clone -b devv https://github.com/ppppangu/unifile.git

# 进入项目目录
cd unifile

# 安装依赖
uv sync
```

---

## 环境配置

### 1. 环境变量配置

- 参考 `.env.example` 文件创建 `.env`
- 编写相关配置参数

### 2. 数据库初始化

```bash
# 初始化数据库表格
uv run python scripts/init_db.py
```

---

## 启动服务

### 1. 启动主应用

```bash
# 启动项目
uv run uvicorn unifiles.app.main:app --host 0.0.0.0 --port 8088
```

### 2. 启动 Celery Worker

#### Windows 环境

> ⚠️ Windows 环境仅支持 solo 模式

```bash
uv run python scripts/start_celery_worker.py --pool solo --loglevel INFO
```

#### Linux 环境

```bash
uv run python scripts/start_celery_worker.py --loglevel INFO
```

---





