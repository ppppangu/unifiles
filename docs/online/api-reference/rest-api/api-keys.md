# API Keys

!!! note
    下列资源响应片段只展示统一 envelope 中的 `data` 内容；完整格式见 REST API 概述。

API 密钥管理接口。

## 创建 API Key

```http
POST /v1/api-keys
```

### 请求

```json
{
    "name": "production-key",
    "scopes": ["files:read", "files:write", "kb:*"],
    "expires_at": "2025-01-15T10:30:00Z"
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `name` | string | 是 | 密钥名称 |
| `scopes` | array | 否 | 权限范围（默认全部） |
| `expires_at` | date-time | 否 | 过期时间 |

### 权限范围

| 范围 | 说明 |
|-----|------|
| `files:read` | 读取文件 |
| `files:write` | 上传/删除文件 |
| `extractions:*` | 内容提取 |
| `kb:read` | 读取知识库 |
| `kb:write` | 管理知识库 |
| `kb:search` | 搜索知识库 |
| `webhooks:*` | 管理 Webhook |
| `*` | 全部权限 |

### 响应

```http
HTTP/1.1 201 Created

{
    "id": "key_abc123",
    "name": "production-key",
    "key": "<issued-key>",
    "scopes": ["files:read", "files:write", "kb:*"],
    "expires_at": "2025-01-15T10:30:00Z",
    "created_at": "2024-01-15T10:30:00Z"
}
```

> **注意**：`key` 字段仅在创建时返回一次，请妥善保存。

---

## 列出 API Keys

```http
GET /v1/api-keys
```

### 响应

```http
HTTP/1.1 200 OK

{
    "items": [
        {
            "id": "key_abc123",
            "name": "production-key",
            "key_prefix": "[REDACTED]x",
            "scopes": ["*"],
            "last_used_at": "2024-01-15T12:00:00Z",
            "expires_at": "2025-01-15T10:30:00Z",
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "total": 3
}
```

---

## 撤销 API Key

```http
DELETE /v1/api-keys/{key_id}
```

### 响应

```http
HTTP/1.1 204 No Content
```

---

## API Key 对象

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 密钥 ID |
| `name` | string | 名称 |
| `key` | string | 密钥值（仅创建时返回） |
| `key_prefix` | string | 密钥前缀（用于识别） |
| `scopes` | array | 权限范围 |
| `last_used_at` | string | 最近使用时间 |
| `expires_at` | string | 过期时间 |
| `created_at` | string | 创建时间 |
