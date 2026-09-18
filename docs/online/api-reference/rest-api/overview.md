# REST API 概述

Unifiles REST API 遵循 RESTful 设计原则，提供文件管理、内容提取和知识库搜索的完整能力。

## 基础信息

### Base URL

```
https://api.unifiles.dev/v1
```

自部署环境请替换为你的服务地址。

### API 版本

当前版本：`v1`

版本号包含在 URL 路径中，未来新版本将使用 `/v2` 等路径。

## 认证

除 `/health` 和 `/v1/health` 外，所有 API 请求必须包含有效的 API Key。

### Header 认证

```http
Authorization: Bearer sk_your_api_key
```

### API Key 格式

```
<live-key>   # 生产环境
<test-key>   # 测试环境
```

### 认证错误

```http
HTTP/1.1 401 Unauthorized

{
    "success": false,
    "error": {
        "code": "INVALID_API_KEY",
        "message": "API Key 无效或已过期"
    }
}
```

## 请求格式

### Content-Type

| 操作 | Content-Type |
|-----|-------------|
| JSON 请求体 | `application/json` |
| 文件上传 | `multipart/form-data` |

### 字符编码

所有请求和响应使用 UTF-8 编码。

### 请求示例

```http
POST /v1/knowledge-bases HTTP/1.1
Host: api.unifiles.dev
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "name": "my-kb",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512
    }
}
```

## 响应格式

### 成功响应

所有 JSON 成功响应使用统一 envelope。单资源放在 `data`：

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "success": true,
    "data": {
        "id": "kb_abc123",
        "name": "my-kb",
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

### 列表响应

分页列表包含 `items` 和 `total`：

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "success": true,
    "data": {
        "items": [
            {"id": "file_001", "filename": "doc1.pdf"},
            {"id": "file_002", "filename": "doc2.pdf"}
        ],
        "total": 100,
        "limit": 50,
        "offset": 0,
        "has_more": true
    }
}
```

### 错误响应

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "success": false,
    "error": {
        "code": "INVALID_REQUEST",
        "message": "请求参数无效",
        "details": {
            "field": "chunk_size",
            "reason": "必须大于 0"
        },
        "request_id": "req_xyz789"
    }
}
```

文件下载端点是唯一例外：成功时直接流式返回原始字节与标准 `Content-Type`、
`Content-Disposition` 响应头。其他成功响应均包含 `success` 与 `data`。

## HTTP 状态码

| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 413 | 请求体过大 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

## 分页

列表 API 支持分页参数：

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `limit` | integer | 50 | 每页数量（最大 100） |
| `offset` | integer | 0 | 偏移量 |

```http
GET /v1/files?limit=20&offset=40
```

## 过滤与排序

### 过滤

使用查询参数过滤：

```http
GET /v1/files?tags=contract&content_type=application/pdf
```

### 排序

```http
GET /v1/files?sort_by=created_at&order=desc
```

| 参数 | 说明 |
|-----|------|
| `sort_by` | 排序字段 |
| `order` | `asc` 升序（默认） / `desc` 降序 |

## 速率限制

部署可以使用 429 表示限流。响应仍使用统一错误 envelope；如果部署提供
`Retry-After`，SDK 会读取它并控制重试等待时间。

```http
HTTP/1.1 429 Too Many Requests

{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "请求过于频繁",
        "retry_after": 30
    }
}
```

## 日期时间格式

所有日期时间使用 ISO 8601 格式（UTC）：

```
2024-01-15T10:30:00Z
```

## 幂等性

创建操作支持幂等性键：

```http
POST /v1/files
Idempotency-Key: unique-request-id-12345
```

相同的 `Idempotency-Key` 在 24 小时内会返回相同的结果。

## SDK 与工具

### 官方 SDK

- [Python SDK](../python-sdk/overview.md)

### HTTP 客户端示例

**cURL:**
```bash
curl -X GET https://api.unifiles.dev/v1/files \
  -H "Authorization: Bearer <api-key>"
```

**Python requests:**
```python
import requests

response = requests.get(
    "https://api.unifiles.dev/v1/files",
    headers={"Authorization": "Bearer <api-key>"}
)
```

**JavaScript fetch:**
```javascript
const response = await fetch("https://api.unifiles.dev/v1/files", {
    headers: {"Authorization": "Bearer <api-key>"}
});
```

## 下一步

- [Files API](files.md) - 文件管理接口
- [Extractions API](extractions.md) - 内容提取接口
- [Knowledge Bases API](knowledge-bases.md) - 知识库接口
- [错误码参考](errors.md) - 完整错误码列表
