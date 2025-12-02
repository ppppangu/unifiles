# 开发技巧

本文档提供 Unifiles 本地开发的实用技巧，帮助你快速搭建开发环境并提高开发效率。

## 开发环境搭建

### 前置要求

```bash
# 必需
- Python 3.11+
- PostgreSQL 15+ (with pgvector)
- Redis 7+
- MinIO 或 S3 兼容存储

# 推荐
- Docker & Docker Compose
- uv (Python 包管理器)
```

### 快速启动

#### 方式一: Docker Compose (推荐)

```bash
# 克隆项目
git clone https://github.com/your-org/unifiles.git
cd unifiles

# 启动基础设施
docker-compose up -d postgres redis minio

# 安装 Python 依赖
uv sync

# 运行数据库迁移
for f in scripts/sql/*.sql; do
    psql -U postgres -d unifiles -f "$f"
done

# 启动开发服务器
uv run uvicorn unifiles.server.main:app --reload --port 8088
```

#### 方式二: 本地服务

```bash
# macOS
brew install postgresql@15 redis minio/stable/minio

# 启动服务
brew services start postgresql@15
brew services start redis
minio server ~/minio-data --console-address ":9001"
```

### 环境配置

创建 `.env` 文件:

```bash
# .env
# 数据库
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=unifiles_dev
PG_USER=postgres
PG_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# 安全 (开发环境)
SECURITY_SECRET_KEY=dev-secret-key-at-least-32-characters

# 调试
DEBUG=true
LOG_LEVEL=DEBUG
```

## 常用开发命令

### 服务管理

```bash
# 启动 API 服务器 (热重载)
uv run uvicorn unifiles.server.main:app --reload --port 8088

# 启动后台 Worker
uv run python -m unifiles.workers.upload_worker
uv run python -m unifiles.workers.extraction_worker

# 同时启动多个服务 (使用 honcho 或 foreman)
# Procfile
# web: uvicorn unifiles.server.main:app --port 8088
# worker1: python -m unifiles.workers.upload_worker
# worker2: python -m unifiles.workers.extraction_worker

honcho start
```

### 代码质量

```bash
# 格式化代码
uv run python scripts/dev/format.py
# 或
uv run ruff format .

# 检查代码风格
uv run python scripts/check/lint.py
# 或
uv run ruff check .

# 类型检查
uv run python scripts/check/type_check.py
# 或
uv run pyright

# 运行所有检查
uv run python scripts/check/validate_all.py
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定文件
uv run pytest tests/unit/test_file_service.py

# 运行特定测试
uv run pytest tests/unit/test_file_service.py::test_upload_file

# 带覆盖率
uv run pytest --cov=unifiles --cov-report=html

# 只运行单元测试
uv run pytest -m unit

# 只运行集成测试
uv run pytest -m integration

# 并行运行
uv run pytest -n auto
```

### 数据库管理

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE unifiles_dev;"

# 安装扩展
psql -U postgres -d unifiles_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d unifiles_dev -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# 运行迁移
for f in scripts/sql/*.sql; do
    echo "Running $f..."
    psql -U postgres -d unifiles_dev -f "$f"
done

# 重置数据库
psql -U postgres -c "DROP DATABASE IF EXISTS unifiles_dev;"
psql -U postgres -c "CREATE DATABASE unifiles_dev;"
# 然后重新运行迁移

# 连接数据库
psql -U postgres -d unifiles_dev
```

## 调试技巧

### 日志配置

```python
# 在代码中临时增加日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用 loguru
from loguru import logger

logger.add("debug.log", level="DEBUG", rotation="10 MB")

# 在请求处理中
logger.debug(f"Processing file: {file_id}")
logger.info(f"File uploaded: {file.filename}")
logger.error(f"Upload failed: {error}")
```

### 断点调试

```python
# 方式一: 使用 breakpoint()
def process_file(file_id: str):
    file = get_file(file_id)
    breakpoint()  # 程序会在这里暂停
    result = extract_content(file)
    return result

# 方式二: 使用 pdb
import pdb
pdb.set_trace()

# 方式三: VS Code 调试配置
# .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI Debug",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "unifiles.server.main:app",
                "--reload",
                "--port", "8088"
            ],
            "jinja": true,
            "justMyCode": false
        }
    ]
}
```

### 请求调试

```python
# 打印完整请求信息的中间件
from starlette.middleware.base import BaseHTTPMiddleware

class DebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print(f"=== Request ===")
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Headers: {dict(request.headers)}")
        
        # 读取 body (注意: 只能读取一次)
        body = await request.body()
        print(f"Body: {body[:1000]}")  # 只打印前 1000 字符
        
        response = await call_next(request)
        
        print(f"=== Response ===")
        print(f"Status: {response.status_code}")
        
        return response
```

### 数据库查询调试

```python
# 记录所有 SQL 查询
import logging
logging.getLogger("asyncpg").setLevel(logging.DEBUG)

# 或使用查询钩子
async def log_query(conn, query, args, timeout):
    logger.debug(f"SQL: {query}")
    logger.debug(f"Args: {args}")

pool = await asyncpg.create_pool(
    ...,
    command_timeout=60,
    setup=lambda conn: conn.add_log_listener(log_query)
)
```

## 性能分析

### 使用 cProfile

```python
import cProfile
import pstats

# 分析函数
def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 你的代码
    result = process_file(file_id)
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)  # 打印前 20 行

# 命令行分析
# python -m cProfile -s cumulative your_script.py
```

### 异步性能分析

```python
import time
from functools import wraps

def async_timer(func):
    """异步函数计时装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

# 使用
@async_timer
async def process_document(doc_id: str):
    ...
```

### 内存分析

```python
# 使用 memory_profiler
from memory_profiler import profile

@profile
def memory_intensive_function():
    data = []
    for i in range(1000000):
        data.append(i)
    return data

# 命令行
# python -m memory_profiler your_script.py
```

## 常见问题排查

### 连接问题

```python
# PostgreSQL 连接失败
async def test_pg_connection():
    try:
        conn = await asyncpg.connect(
            host=settings.database.host,
            port=settings.database.port,
            user=settings.database.user,
            password=settings.database.password,
            database=settings.database.name
        )
        await conn.execute("SELECT 1")
        print("PostgreSQL connection OK")
        await conn.close()
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")

# Redis 连接失败
async def test_redis_connection():
    try:
        redis = aioredis.from_url(settings.redis_url)
        await redis.ping()
        print("Redis connection OK")
        await redis.close()
    except Exception as e:
        print(f"Redis connection failed: {e}")

# MinIO 连接失败
def test_minio_connection():
    try:
        client = Minio(
            settings.minio.endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            secure=settings.minio.secure
        )
        buckets = client.list_buckets()
        print(f"MinIO connection OK, buckets: {[b.name for b in buckets]}")
    except Exception as e:
        print(f"MinIO connection failed: {e}")
```

### pgvector 问题

```sql
-- 检查扩展是否安装
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 检查向量列类型
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'chunks' AND column_name = 'embedding';

-- 测试向量查询
SELECT id, embedding <=> '[0.1,0.2,...]'::vector as distance
FROM chunks
ORDER BY distance
LIMIT 5;
```

### Worker 问题

```python
# 检查队列状态
async def check_queue_status():
    redis = await get_redis()
    
    # 获取队列长度
    queue_len = await redis.llen("upload_queue")
    print(f"Upload queue length: {queue_len}")
    
    # 查看队列内容 (不移除)
    items = await redis.lrange("upload_queue", 0, 10)
    for item in items:
        print(f"Queue item: {item}")

# 清空队列 (谨慎使用)
async def clear_queue(queue_name: str):
    redis = await get_redis()
    await redis.delete(queue_name)
    print(f"Queue {queue_name} cleared")
```

## IDE 配置

### VS Code 推荐配置

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.analysis.typeCheckingMode": "basic",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    },
    "ruff.lint.args": ["--config=pyproject.toml"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

### 推荐扩展

```json
// .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "mtxr.sqltools",
        "mtxr.sqltools-driver-pg",
        "humao.rest-client"
    ]
}
```

### REST Client 测试文件

```http
# api-tests.http

### 健康检查
GET http://localhost:8088/health

### 上传文件
POST http://localhost:8088/api/v1/files
Authorization: Bearer [REDACTED]
Content-Type: multipart/form-data; boundary=----FormBoundary

------FormBoundary
Content-Disposition: form-data; name="file"; filename="test.pdf"
Content-Type: application/pdf

< ./test.pdf
------FormBoundary--

### 获取文件列表
GET http://localhost:8088/api/v1/files
Authorization: Bearer [REDACTED]

### 创建知识库
POST http://localhost:8088/api/v1/knowledge-bases
Authorization: Bearer [REDACTED]
Content-Type: application/json

{
    "name": "test-kb",
    "description": "Test knowledge base"
}

### 搜索
POST http://localhost:8088/api/v1/knowledge-bases/kb_xxx/search
Authorization: Bearer [REDACTED]
Content-Type: application/json

{
    "query": "test query",
    "top_k": 5
}
```

## Git 工作流

### 提交规范

```bash
# 提交消息格式
<type>(<scope>): <subject>

# 类型
feat:     新功能
fix:      修复 bug
docs:     文档更新
style:    代码格式 (不影响功能)
refactor: 重构
perf:     性能优化
test:     测试
chore:    构建/工具变更

# 示例
feat(api): add file batch upload endpoint
fix(ocr): handle empty page correctly
docs(readme): update installation instructions
```

### 分支策略

```bash
main          # 主分支，生产代码
├── develop   # 开发分支
├── feature/* # 功能分支
├── fix/*     # 修复分支
└── release/* # 发布分支

# 创建功能分支
git checkout -b feature/add-batch-upload develop

# 完成后合并
git checkout develop
git merge --no-ff feature/add-batch-upload
git branch -d feature/add-batch-upload
```

### Pre-commit 钩子

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

# 安装
pip install pre-commit
pre-commit install
```

## 下一步

- [自部署指南](../self-hosting/) - 生产环境部署
- [API 参考](../api-reference/) - 完整 API 文档
