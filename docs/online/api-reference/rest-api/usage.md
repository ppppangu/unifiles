# Usage API

使用量统计和配额查询接口。

## 获取使用统计

```http
GET /v1/usage/stats
```

### 响应

```http
HTTP/1.1 200 OK

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
        "total_count": 156
    },
    "api_keys": {
        "count": 3,
        "limit": 10
    },
    "webhooks": {
        "count": 5,
        "limit": 20
    },
    "period": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-31T23:59:59Z"
    }
}
```

---

## 获取配额限制

```http
GET /v1/usage/limits
```

### 响应

```http
HTTP/1.1 200 OK

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

---

## 响应字段说明

### storage（存储）

| 字段 | 类型 | 说明 |
|-----|------|------|
| `used_bytes` | integer | 已用存储（字节） |
| `limit_bytes` | integer | 存储上限 |
| `used_percentage` | float | 使用百分比 |

### extraction（提取）

| 字段 | 类型 | 说明 |
|-----|------|------|
| `pages_used` | integer | 本月已提取页数 |
| `pages_limit` | integer | 月度页数上限 |
| `reset_at` | string | 配额重置时间 |

### rate_limits（速率限制）

| 字段 | 类型 | 说明 |
|-----|------|------|
| `api_requests_per_minute` | integer | 每分钟 API 请求数 |
| `file_uploads_per_minute` | integer | 每分钟上传数 |
| `search_requests_per_minute` | integer | 每分钟搜索数 |
