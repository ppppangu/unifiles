# Configuration

本文档介绍如何配置 Unifiles。

## 环境变量

Unifiles 支持通过环境变量进行配置：

### 数据库配置

```bash
PG_HOST=localhost          # PostgreSQL 主机地址
PG_PORT=5432               # PostgreSQL 端口
PG_DATABASE=unifiles       # 数据库名称
PG_USER=postgres           # 数据库用户
PG_PASSWORD=your_password  # 数据库密码
```

### Redis 配置

```bash
REDIS_HOST=localhost    # Redis 主机地址
REDIS_PORT=6379         # Redis 端口
REDIS_DB=0              # Redis 数据库编号
```

### MinIO 配置

```bash
MINIO_ENDPOINT=localhost:9000  # MinIO 端点
MINIO_ACCESS_KEY=minioadmin    # 访问密钥
MINIO_SECRET_KEY=minioadmin    # 密钥
MINIO_USE_SSL=false            # 是否使用 SSL
```

### 安全配置

```bash
SECURITY_SECRET_KEY=your-secret-key-at-least-32-chars  # JWT 密钥（必需，至少32字符）
```

### 应用配置

```bash
APP_ENV=development    # 运行环境 (development/production)
APP_DEBUG=true         # 调试模式
APP_LOG_LEVEL=INFO     # 日志级别 (DEBUG/INFO/WARNING/ERROR)
```

## 配置文件

除了环境变量，Unifiles 也支持使用 `.env` 文件：

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
vim .env
```

## 日志配置

### 日志级别

可通过 `APP_LOG_LEVEL` 环境变量设置日志级别：

- `DEBUG`: 详细的调试信息
- `INFO`: 一般信息（默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息

### 日志输出

开发模式下，日志会输出到控制台。生产模式下建议配置日志文件：

```bash
LOG_FILE=/var/log/unifiles/app.log
LOG_MAX_SIZE=10485760  # 10MB
LOG_BACKUP_COUNT=5
```

## 性能配置

### 连接池

```bash
PG_POOL_MIN_SIZE=10      # 最小连接数
PG_POOL_MAX_SIZE=20      # 最大连接数
REDIS_POOL_MAX_SIZE=10   # Redis 连接池大小
```

### Worker 配置

```bash
WORKER_CONCURRENCY=4      # Worker 并发数
WORKER_MAX_RETRIES=3      # 最大重试次数
WORKER_RETRY_DELAY=60     # 重试延迟（秒）
```

## 下一步

- [故障排查](troubleshooting.md) - 解决常见问题
- [部署指南](deployment.md) - 生产环境部署
