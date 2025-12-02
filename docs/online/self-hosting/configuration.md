# 配置说明

本文档详细介绍 Unifiles 的所有配置选项，包括环境变量、配置文件和运行时配置。

## 配置优先级

配置加载顺序 (后者覆盖前者):

```
1. 代码默认值
2. .env 文件
3. 环境变量
4. 运行时配置 (Redis ConfigStore)
```

## 环境变量

### 数据库配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `PG_HOST` | PostgreSQL 主机地址 | `localhost` | 是 |
| `PG_PORT` | PostgreSQL 端口 | `5432` | 否 |
| `PG_DATABASE` | 数据库名称 | `unifiles` | 是 |
| `PG_USER` | 数据库用户名 | `postgres` | 是 |
| `PG_PASSWORD` | 数据库密码 | - | 是 |
| `PG_POOL_MIN` | 连接池最小连接数 | `5` | 否 |
| `PG_POOL_MAX` | 连接池最大连接数 | `20` | 否 |
| `PG_SSL_MODE` | SSL 模式 | `prefer` | 否 |

### Redis 配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `REDIS_HOST` | Redis 主机地址 | `localhost` | 是 |
| `REDIS_PORT` | Redis 端口 | `6379` | 否 |
| `REDIS_DB` | 数据库编号 | `0` | 否 |
| `REDIS_PASSWORD` | 密码 | - | 否 |
| `REDIS_URL` | 完整连接 URL | - | 否 |

如果设置了 `REDIS_URL`，将忽略其他 Redis 配置:

```bash
REDIS_URL=redis://:password@localhost:6379/0
```

### MinIO/S3 配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `MINIO_ENDPOINT` | MinIO 服务地址 | `localhost:9000` | 是 |
| `MINIO_ACCESS_KEY` | 访问密钥 | - | 是 |
| `MINIO_SECRET_KEY` | 秘密密钥 | - | 是 |
| `MINIO_SECURE` | 使用 HTTPS | `false` | 否 |
| `MINIO_REGION` | 区域 | `us-east-1` | 否 |
| `MINIO_BUCKET_RAW` | 原始文件桶 | `unifiles-raw` | 否 |
| `MINIO_BUCKET_PROCESSED` | 处理文件桶 | `unifiles-processed` | 否 |

### 安全配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `SECURITY_SECRET_KEY` | JWT/加密密钥 | - | 是 |
| `SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌过期时间 | `30` | 否 |
| `SECURITY_REFRESH_TOKEN_EXPIRE_DAYS` | 刷新令牌过期时间 | `7` | 否 |
| `SECURITY_ALGORITHM` | JWT 算法 | `HS256` | 否 |
| `ENCRYPTION_KEY` | 数据加密密钥 | - | 否 |

**重要**: `SECURITY_SECRET_KEY` 必须至少 32 个字符。

### API 服务配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `API_HOST` | 监听地址 | `0.0.0.0` | 否 |
| `API_PORT` | 监听端口 | `8088` | 否 |
| `API_WORKERS` | Worker 进程数 | `1` | 否 |
| `DEBUG` | 调试模式 | `false` | 否 |
| `LOG_LEVEL` | 日志级别 | `INFO` | 否 |

### 速率限制配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `RATE_LIMIT_ENABLED` | 启用速率限制 | `true` | 否 |
| `RATE_LIMIT_DEFAULT` | 默认请求数/分钟 | `1000` | 否 |
| `RATE_LIMIT_ANONYMOUS` | 匿名请求数/分钟 | `100` | 否 |

### 文件处理配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `MAX_UPLOAD_SIZE_MB` | 最大上传大小 | `100` | 否 |
| `ALLOWED_FILE_TYPES` | 允许的文件类型 | `pdf,docx,xlsx,pptx,txt,md,html` | 否 |
| `OCR_PROVIDER` | OCR 提供商 | `internal` | 否 |
| `OCR_TIMEOUT_SECONDS` | OCR 超时时间 | `300` | 否 |

### 嵌入模型配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `EMBEDDING_PROVIDER` | 嵌入提供商 | `openai` | 否 |
| `EMBEDDING_MODEL` | 模型名称 | `text-embedding-3-small` | 否 |
| `EMBEDDING_DIMENSIONS` | 向量维度 | `1536` | 否 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - | 条件 |
| `OPENAI_BASE_URL` | OpenAI 基础 URL | - | 否 |

### 可观测性配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `OTEL_ENABLED` | 启用 OpenTelemetry | `false` | 否 |
| `OTEL_SERVICE_NAME` | 服务名称 | `unifiles` | 否 |
| `OTEL_EXPORTER_ENDPOINT` | 导出器端点 | `localhost:4317` | 否 |
| `METRICS_ENABLED` | 启用指标 | `true` | 否 |
| `METRICS_PORT` | 指标端口 | `9090` | 否 |

## 配置文件示例

### 开发环境

```bash
# .env.development

# 数据库
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=unifiles_dev
PG_USER=postgres
PG_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# 安全
SECURITY_SECRET_KEY=dev-secret-key-not-for-production-use

# 调试
DEBUG=true
LOG_LEVEL=DEBUG

# 速率限制 (开发环境禁用)
RATE_LIMIT_ENABLED=false
```

### 生产环境

```bash
# .env.production

# 数据库
PG_HOST=pg-cluster.internal
PG_PORT=5432
PG_DATABASE=unifiles
PG_USER=unifiles
PG_PASSWORD=${PG_PASSWORD}  # 从密钥管理器获取
PG_POOL_MIN=10
PG_POOL_MAX=50
PG_SSL_MODE=require

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis-cluster.internal:6379/0

# MinIO/S3
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=${AWS_ACCESS_KEY_ID}
MINIO_SECRET_KEY=${AWS_SECRET_ACCESS_KEY}
MINIO_SECURE=true
MINIO_REGION=ap-northeast-1

# 安全
SECURITY_SECRET_KEY=${SECURITY_SECRET_KEY}
SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES=15
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# API
API_HOST=0.0.0.0
API_PORT=8088
API_WORKERS=4
DEBUG=false
LOG_LEVEL=INFO

# 速率限制
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=1000

# 文件处理
MAX_UPLOAD_SIZE_MB=100
OCR_TIMEOUT_SECONDS=600

# 嵌入
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=${OPENAI_API_KEY}

# 可观测性
OTEL_ENABLED=true
OTEL_SERVICE_NAME=unifiles-prod
OTEL_EXPORTER_ENDPOINT=otel-collector.internal:4317
METRICS_ENABLED=true
```

## 运行时配置

运行时配置存储在 Redis 中，可以动态修改无需重启服务。

### 使用 API 修改

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 获取配置
config = client.admin.get_config("rate_limit_enabled")
print(config)  # True

# 设置配置
client.admin.set_config("rate_limit_enabled", False)
```

### 使用 CLI 修改

```bash
# 获取配置
unifiles config get rate_limit_enabled

# 设置配置
unifiles config set rate_limit_enabled false

# 列出所有配置
unifiles config list
```

### 支持的运行时配置

| 键 | 描述 | 类型 |
|----|------|------|
| `rate_limit_enabled` | 速率限制开关 | bool |
| `rate_limit_default` | 默认速率限制 | int |
| `max_upload_size_mb` | 最大上传大小 | int |
| `enable_quota_check` | 配额检查开关 | bool |
| `maintenance_mode` | 维护模式 | bool |

## 配置验证

### 启动时验证

服务启动时会验证必需配置:

```python
from unifiles.core.config.settings import settings

# 验证配置
settings.validate()

# 如果缺少必需配置，会抛出异常
# ConfigurationError: Missing required configuration: SECURITY_SECRET_KEY
```

### 手动验证

```bash
# 验证配置文件
python -c "
from unifiles.core.config.settings import settings
settings.validate()
print('Configuration is valid')
"
```

## 敏感配置处理

### 使用环境变量

```bash
# 不要在文件中存储敏感信息
export PG_PASSWORD="your_secure_password"
export SECURITY_SECRET_KEY="your_secret_key"
```

### 使用密钥管理器

```python
# 集成 AWS Secrets Manager
import boto3

def get_secret(secret_name: str) -> str:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

# 在启动脚本中
os.environ['PG_PASSWORD'] = get_secret('unifiles/pg_password')
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: unifiles-secrets
type: Opaque
stringData:
  PG_PASSWORD: "your_password"
  SECURITY_SECRET_KEY: "your_secret_key"

---
# 在 Deployment 中引用
env:
  - name: PG_PASSWORD
    valueFrom:
      secretKeyRef:
        name: unifiles-secrets
        key: PG_PASSWORD
```

## 多环境配置

### 使用配置文件切换

```bash
# 开发环境
cp .env.development .env
docker-compose up

# 生产环境
cp .env.production .env
docker-compose -f docker-compose.prod.yml up
```

### 使用环境变量覆盖

```bash
# 基础配置
source .env.base

# 环境特定覆盖
export PG_HOST=production-db.internal
export DEBUG=false
```

## 下一步

- [数据库设置](./database-setup.md) - PostgreSQL 详细配置
- [存储设置](./storage-setup.md) - MinIO/S3 详细配置
- [可观测性](./observability.md) - 监控配置
