# Files API

文件管理接口，提供文件上传、列表、下载和删除功能。

## 上传文件

上传新文件到 Unifiles。

```http
POST /v1/files
```

### 请求

**Headers:**
```http
Authorization: Bearer sk_...
Content-Type: multipart/form-data
```

**Form Data:**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `file` | file | 是 | 文件内容 |
| `metadata` | string | 否 | JSON 格式的元数据 |
| `tags` | string | 否 | 逗号分隔的标签 |

### 示例

```bash
curl -X POST https://api.unifiles.dev/v1/files \
  -H "Authorization: Bearer sk_..." \
  -F "file=@document.pdf" \
  -F 'metadata={"project":"legal","year":2024}' \
  -F "tags=contract,important"
```

### 响应

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
    "id": "file_abc123xyz",
    "filename": "document.pdf",
    "content_type": "application/pdf",
    "size": 1048576,
    "metadata": {
        "project": "legal",
        "year": 2024
    },
    "tags": ["contract", "important"],
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 400 | `INVALID_FILE` | 文件无效 |
| 413 | `FILE_TOO_LARGE` | 文件过大 |
| 415 | `UNSUPPORTED_FORMAT` | 不支持的格式 |

---

## 列出文件

获取文件列表，支持分页和过滤。

```http
GET /v1/files
```

### 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `limit` | integer | 50 | 每页数量（最大 100） |
| `offset` | integer | 0 | 偏移量 |
| `tags` | string | - | 按标签过滤（逗号分隔） |
| `content_type` | string | - | 按 MIME 类型过滤 |
| `sort_by` | string | `created_at` | 排序字段 |
| `order` | string | `desc` | 排序方向 |

### 示例

```bash
curl -X GET "https://api.unifiles.dev/v1/files?limit=20&tags=contract" \
  -H "Authorization: Bearer sk_..."
```

### 响应

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "items": [
        {
            "id": "file_abc123",
            "filename": "contract.pdf",
            "content_type": "application/pdf",
            "size": 524288,
            "tags": ["contract"],
            "created_at": "2024-01-15T10:30:00Z"
        },
        {
            "id": "file_def456",
            "filename": "agreement.pdf",
            "content_type": "application/pdf",
            "size": 262144,
            "tags": ["contract", "signed"],
            "created_at": "2024-01-14T09:00:00Z"
        }
    ],
    "total": 42,
    "limit": 20,
    "offset": 0
}
```

---

## 获取文件详情

获取单个文件的详细信息。

```http
GET /v1/files/{file_id}
```

### 路径参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `file_id` | string | 文件 ID |

### 示例

```bash
curl -X GET https://api.unifiles.dev/v1/files/file_abc123 \
  -H "Authorization: Bearer sk_..."
```

### 响应

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": "file_abc123",
    "filename": "document.pdf",
    "content_type": "application/pdf",
    "size": 1048576,
    "metadata": {
        "project": "legal",
        "year": 2024
    },
    "tags": ["contract", "important"],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 404 | `FILE_NOT_FOUND` | 文件不存在 |

---

## 下载文件

下载文件内容。

```http
GET /v1/files/{file_id}/download
```

### 路径参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `file_id` | string | 文件 ID |

### 示例

```bash
curl -X GET https://api.unifiles.dev/v1/files/file_abc123/download \
  -H "Authorization: Bearer sk_..." \
  -o downloaded.pdf
```

### 响应

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="document.pdf"

<binary content>
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 404 | `FILE_NOT_FOUND` | 文件不存在 |

---

## 删除文件

删除文件及其关联的提取结果和知识库文档。

```http
DELETE /v1/files/{file_id}
```

### 路径参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `file_id` | string | 文件 ID |

### 示例

```bash
curl -X DELETE https://api.unifiles.dev/v1/files/file_abc123 \
  -H "Authorization: Bearer sk_..."
```

### 响应

```http
HTTP/1.1 204 No Content
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 404 | `FILE_NOT_FOUND` | 文件不存在 |

---

## 获取支持的文件类型

获取系统支持的文件类型列表。

```http
GET /v1/files/types
```

### 示例

```bash
curl -X GET https://api.unifiles.dev/v1/files/types \
  -H "Authorization: Bearer sk_..."
```

### 响应

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "types": [
        {
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "description": "PDF 文档",
            "max_size_mb": 100
        },
        {
            "extension": ".docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "description": "Word 文档",
            "max_size_mb": 100
        },
        {
            "extension": ".png",
            "mime_type": "image/png",
            "description": "PNG 图片",
            "max_size_mb": 20
        }
    ]
}
```

---

## File 对象

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 文件唯一标识 |
| `filename` | string | 原始文件名 |
| `content_type` | string | MIME 类型 |
| `size` | integer | 文件大小（字节） |
| `metadata` | object | 自定义元数据 |
| `tags` | array | 标签列表 |
| `created_at` | string | 创建时间（ISO 8601） |
| `updated_at` | string | 更新时间（ISO 8601） |
