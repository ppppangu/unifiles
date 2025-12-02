# 速率限制

Unifiles 对 API 请求实施速率限制，以确保服务的稳定性和公平使用。了解这些限制有助于你设计更健壮的应用。

## 限制概览

### 请求速率限制

| 端点类型 | 限制 | 时间窗口 |
|---------|------|---------|
| 通用 API | 1000 请求 | 每分钟 |
| 文件上传 | 100 请求 | 每分钟 |
| 搜索 | 300 请求 | 每分钟 |
| 提取任务 | 50 请求 | 每分钟 |

### 资源配额限制

| 资源 | 免费版 | 专业版 | 企业版 |
|-----|--------|--------|--------|
| 存储空间 | 1 GB | 100 GB | 无限制 |
| 每月提取页数 | 1,000 页 | 50,000 页 | 无限制 |
| 知识库数量 | 5 个 | 50 个 | 无限制 |
| 每知识库文档数 | 100 个 | 10,000 个 | 无限制 |
| API 密钥数量 | 2 个 | 10 个 | 无限制 |
| Webhook 数量 | 3 个 | 20 个 | 无限制 |

### 单请求限制

| 限制项 | 值 |
|-------|-----|
| 单文件最大大小 | 100 MB |
| 请求体最大大小 | 10 MB |
| 单次搜索 top_k 最大值 | 100 |
| 批量操作最大数量 | 100 |

## 响应头信息

每个 API 响应都包含速率限制相关的头信息：

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1705312800
X-RateLimit-Reset-After: 45
```

| Header | 说明 |
|--------|------|
| `X-RateLimit-Limit` | 当前时间窗口的总配额 |
| `X-RateLimit-Remaining` | 剩余配额 |
| `X-RateLimit-Reset` | 配额重置的 Unix 时间戳 |
| `X-RateLimit-Reset-After` | 距离配额重置的秒数 |

## 超出限制的响应

当超出速率限制时，API 返回 `429 Too Many Requests`：

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 30

{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "请求过于频繁，请稍后重试",
        "retry_after": 30
    }
}
```

## SDK 中的速率限制处理

### 自动重试

SDK 默认会自动处理速率限制，进行指数退避重试：

```python
from unifiles import UnifilesClient

# 默认配置：自动重试3次
client = UnifilesClient(
    api_key="sk_...",
    max_retries=3  # 默认值
)

# 禁用自动重试
client = UnifilesClient(
    api_key="sk_...",
    max_retries=0
)
```

### 手动处理速率限制

```python
from unifiles import UnifilesClient
from unifiles.exceptions import RateLimitError
import time

client = UnifilesClient(api_key="sk_...", max_retries=0)

def upload_with_retry(file_path, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return client.files.upload(file_path)
        except RateLimitError as e:
            if attempt < max_attempts - 1:
                wait_time = e.retry_after or (2 ** attempt)
                print(f"速率限制，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                raise

file = upload_with_retry("document.pdf")
```

### 获取当前配额状态

```python
# 获取使用统计
usage = client.usage.get_stats()

print(f"本月已用存储: {usage.storage_used_mb} MB")
print(f"存储配额: {usage.storage_limit_mb} MB")
print(f"本月提取页数: {usage.extraction_pages_used}")
print(f"提取配额: {usage.extraction_pages_limit}")

# 获取限制详情
limits = client.usage.get_limits()

print(f"API 请求限制: {limits.api_requests_per_minute}/分钟")
print(f"文件上传限制: {limits.file_uploads_per_minute}/分钟")
```

## REST API

### 获取使用统计

```http
GET /v1/usage/stats
Authorization: Bearer sk_...
```

**响应：**

```json
{
    "storage": {
        "used_bytes": 524288000,
        "limit_bytes": 107374182400,
        "used_percentage": 0.49
    },
    "extraction": {
        "pages_used": 1250,
        "pages_limit": 50000,
        "reset_at": "2024-02-01T00:00:00Z"
    },
    "knowledge_bases": {
        "count": 8,
        "limit": 50
    },
    "documents": {
        "total_count": 156,
        "by_kb_limit": 10000
    },
    "api_keys": {
        "count": 3,
        "limit": 10
    },
    "webhooks": {
        "count": 5,
        "limit": 20
    }
}
```

### 获取限制详情

```http
GET /v1/usage/limits
Authorization: Bearer sk_...
```

**响应：**

```json
{
    "rate_limits": {
        "api_requests_per_minute": 1000,
        "file_uploads_per_minute": 100,
        "search_requests_per_minute": 300,
        "extraction_requests_per_minute": 50
    },
    "resource_limits": {
        "storage_bytes": 107374182400,
        "extraction_pages_per_month": 50000,
        "knowledge_bases": 50,
        "documents_per_kb": 10000,
        "api_keys": 10,
        "webhooks": 20
    },
    "request_limits": {
        "max_file_size_bytes": 104857600,
        "max_request_body_bytes": 10485760,
        "max_search_top_k": 100,
        "max_batch_size": 100
    },
    "plan": "professional"
}
```

## 最佳实践

### 1. 实现指数退避

```python
import time
import random

def exponential_backoff(attempt, base_delay=1, max_delay=60):
    """计算指数退避延迟时间"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    # 添加随机抖动
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter

def api_call_with_backoff(func, *args, max_attempts=5, **kwargs):
    """带指数退避的 API 调用"""
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            if attempt < max_attempts - 1:
                delay = e.retry_after or exponential_backoff(attempt)
                time.sleep(delay)
            else:
                raise
```

### 2. 批量操作时控制速率

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_files_with_rate_limit(file_paths, rate_per_second=10):
    """以受控速率处理文件"""
    interval = 1.0 / rate_per_second
    results = []
    
    for i, path in enumerate(file_paths):
        start_time = time.time()
        
        file = client.files.upload(path)
        results.append(file)
        
        # 控制速率
        elapsed = time.time() - start_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        
        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1}/{len(file_paths)} 个文件")
    
    return results
```

### 3. 监控配额使用

```python
def check_quota_before_operation(required_pages=0, required_storage_mb=0):
    """在操作前检查配额"""
    usage = client.usage.get_stats()
    
    # 检查存储配额
    available_storage = usage.storage.limit_bytes - usage.storage.used_bytes
    if required_storage_mb * 1024 * 1024 > available_storage:
        raise Exception("存储配额不足")
    
    # 检查提取页数配额
    available_pages = usage.extraction.pages_limit - usage.extraction.pages_used
    if required_pages > available_pages:
        raise Exception("本月提取页数配额不足")
    
    return True

# 使用示例
def upload_and_extract(file_path, estimated_pages=10):
    # 先检查配额
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    check_quota_before_operation(
        required_pages=estimated_pages,
        required_storage_mb=file_size_mb
    )
    
    # 执行操作
    file = client.files.upload(file_path)
    extraction = client.extractions.create(file_id=file.id)
    return extraction
```

### 4. 使用 Webhook 减少轮询

```python
# 不推荐：频繁轮询消耗配额
while True:
    extraction = client.extractions.get(extraction_id)
    if extraction.status in ["completed", "failed"]:
        break
    time.sleep(1)  # 每秒消耗一次 API 配额

# 推荐：使用 Webhook
webhook = client.webhooks.create(
    url="https://your-app.com/webhook",
    events=["extraction.completed", "extraction.failed"]
)

# 创建提取任务后无需轮询
extraction = client.extractions.create(file_id=file.id)
# Webhook 会在完成时通知你
```

### 5. 缓存搜索结果

```python
from functools import lru_cache
import hashlib

# 使用 LRU 缓存减少重复搜索
@lru_cache(maxsize=1000)
def cached_search(kb_id, query, top_k):
    """缓存搜索结果"""
    return client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=top_k
    )

# 或使用 Redis 缓存
import redis
import json

redis_client = redis.Redis()

def search_with_cache(kb_id, query, top_k, cache_ttl=300):
    """使用 Redis 缓存搜索结果"""
    cache_key = f"search:{kb_id}:{hashlib.md5(query.encode()).hexdigest()}:{top_k}"
    
    # 尝试从缓存获取
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 执行搜索
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=top_k
    )
    
    # 缓存结果
    redis_client.setex(cache_key, cache_ttl, json.dumps(results.dict()))
    
    return results
```

## 配额提升

如果你需要更高的配额限制：

### 升级计划

不同计划提供不同的配额上限：

| 功能 | 免费版 | 专业版 | 企业版 |
|-----|--------|--------|--------|
| 月费 | ¥0 | ¥299 | 联系销售 |
| 存储 | 1 GB | 100 GB | 无限制 |
| 提取页数 | 1,000/月 | 50,000/月 | 无限制 |
| API 速率 | 100/分钟 | 1,000/分钟 | 自定义 |

### 临时提升

对于短期活动或促销，可以申请临时配额提升：

```python
# 联系支持团队
# support@unifiles.dev
```

### 企业定制

企业客户可以获得：

- 自定义速率限制
- 专属资源池
- SLA 保障
- 优先技术支持

## 下一步

- [错误处理](error-handling.md) - 处理各种 API 错误
- [批量处理](../cookbook/intermediate/batch-processing.md) - 高效处理大量文件
- [Webhooks](webhooks.md) - 使用 Webhook 减少轮询
