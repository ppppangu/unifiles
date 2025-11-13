# Unifiles 部署

## Linux服务器部署

### 使用Supabase PostgreSQL官方镜像

#### 生产环境优化版本
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

#### 验证部署
```bash
# 检查容器状态
docker ps | grep supabase-postgres

# 查看容器日志
docker logs supabase-postgres

# 测试数据库连接
docker exec -it supabase-postgres psql -U postgres -c "SELECT version();"
```

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| POSTGRES_USER | 数据库超级用户 | postgres |
| POSTGRES_PASSWORD | 用户密码 | 必须设置 |
| POSTGRES_DB | 默认数据库 | postgres |
| PGDATA | 数据目录 | /var/lib/postgresql/data/pgdata |

### 数据持久化

- `supabase-postgres-data`: PostgreSQL数据文件持久化
- `supabase-postgres-config`: 配置文件持久化（可选）

### 网络和端口

- 默认端口：5432
- 确保防火墙开放对应端口
- 生产环境建议使用反向代理和SSL证书

### 部署RabbitMQ

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

### 检查RabbitMQ是否部署成功

```
docker logs rabbitmq
```

### 部署convert2pdf服务
[convert2pdf服务部署](https://github.com/ppppangu/convert2pdf_server)

### 需要自行部署embedding服务和VL模型服务
目前测试Qwen3-8B-VL模型可用
bge-m3模型可用


# 如何在本地部署该项目
```
git clone -b devv https://github.com/ppppangu/unifile.git

cd unifile

uv sync
```

## 配置环境 `.env`
### 参考 `.example.env` 创建并编写`.env`中相关配置


## 启动项目
```
# 启动项目
uv run uvicorn unifiles.app.main:app --host 0.0.0.0 --port 8088
```

# 启动Celery Worker
## Windows环境启动celery仅支持solo模式
```
uv run python scripts/start_celery_worker.py --pool solo --loglevel INFO
```
## Linux环境启动celery
```
uv run python scripts/start_celery_worker.py --loglevel INFO
```





