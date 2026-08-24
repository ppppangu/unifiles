# Webhooks API

!!! note
    下列资源响应片段只展示统一 envelope 中的 `data` 内容；完整格式见 REST API 概述。

Webhook 管理接口，配置异步事件通知。

## 创建 Webhook

```http
POST /v1/webhooks
```

### 请求

```json
{
    "url": "https://your-app.com/webhook/unifiles",
    "events": [
        "extraction.completed",
        "extraction.failed",
        "document.indexed"
    ],
    "secret": "your_webhook_secret"
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `url` | string | 是 | Webhook 接收 URL（HTTPS） |
| `events` | array | 是 | 订阅的事件类型 |
| `secret` | string | 否 | 签名密钥 |

### 响应

```http
HTTP/1.1 201 Created

{
    "id": "wh_abc123",
    "url": "https://your-app.com/webhook/unifiles",
    "events": ["extraction.completed", "extraction.failed", "document.indexed"],
    "enabled": true,
    "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 列出 Webhooks

```http
GET /v1/webhooks
```

### 响应

```http
HTTP/1.1 200 OK

{
    "items": [
        {
            "id": "wh_abc123",
            "url": "https://your-app.com/webhook/unifiles",
            "events": ["extraction.completed"],
            "enabled": true,
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "total": 3
}
```

---

## 获取 Webhook 详情

```http
GET /v1/webhooks/{webhook_id}
```

### 响应

```http
HTTP/1.1 200 OK

{
    "id": "wh_abc123",
    "url": "https://your-app.com/webhook/unifiles",
    "events": ["extraction.completed", "document.indexed"],
    "enabled": true,
    "last_delivery_at": "2024-01-15T12:00:00Z",
    "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 更新 Webhook

```http
PATCH /v1/webhooks/{webhook_id}
```

### 请求

```json
{
    "events": ["extraction.completed"],
    "enabled": false
}
```

### 响应

```http
HTTP/1.1 200 OK

{
    "id": "wh_abc123",
    "url": "https://your-app.com/webhook/unifiles",
    "events": ["extraction.completed"],
    "enabled": false,
    ...
}
```

---

## 删除 Webhook

```http
DELETE /v1/webhooks/{webhook_id}
```

### 响应

```http
HTTP/1.1 204 No Content
```

---

## 支持的事件

### 文件事件

| 事件 | 说明 |
|-----|------|
| `file.uploaded` | 文件上传成功 |
| `file.deleted` | 文件被删除 |

### 提取事件

| 事件 | 说明 |
|-----|------|
| `extraction.started` | 提取任务开始 |
| `extraction.completed` | 提取成功完成 |
| `extraction.failed` | 提取失败 |

### 文档事件

| 事件 | 说明 |
|-----|------|
| `document.indexing` | 文档开始索引 |
| `document.indexed` | 文档索引完成 |
| `document.index_failed` | 文档索引失败 |
| `document.deleted` | 文档被删除 |

### 知识库事件

| 事件 | 说明 |
|-----|------|
| `knowledge_base.created` | 知识库创建 |
| `knowledge_base.deleted` | 知识库删除 |

---

## Webhook 请求格式

Unifiles 发送的 Webhook 请求格式：

```http
POST /webhook/unifiles HTTP/1.1
Host: your-app.com
Content-Type: application/json
X-Unifiles-Signature: sha256=abc123...
X-Unifiles-Event: extraction.completed
X-Unifiles-Delivery: del_xyz789

{
    "id": "evt_abc123",
    "type": "extraction.completed",
    "created_at": "2024-01-15T10:35:00Z",
    "data": {
        "extraction_id": "ext_xyz789",
        "file_id": "file_abc123",
        "status": "completed",
        "total_pages": 15
    }
}
```

### 请求头

| Header | 说明 |
|--------|------|
| `X-Unifiles-Signature` | 请求签名 |
| `X-Unifiles-Event` | 事件类型 |
| `X-Unifiles-Delivery` | 投递 ID |

### 签名验证

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected}")
```

---

## Webhook 对象

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | Webhook ID |
| `url` | string | 接收 URL |
| `events` | array | 订阅的事件 |
| `enabled` | boolean | 是否启用 |
| `last_delivery_at` | string | 最近投递时间 |
| `created_at` | string | 创建时间 |
