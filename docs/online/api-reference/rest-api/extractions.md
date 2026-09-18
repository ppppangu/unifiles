# Extractions API

内容提取接口，从上传的文件中提取结构化的 Markdown 内容。

!!! note
    下列资源响应片段只展示统一 envelope 中的 `data` 内容；完整格式见 REST API 概述。

## 创建提取任务

为指定文件创建内容提取任务。

```http
POST /v1/extractions
```

### 请求

```json
{
    "file_id": "file_abc123",
    "mode": "normal",
    "options": {
        "language": "zh",
        "ocr_provider": "default"
    }
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `file_id` | string | 是 | 文件 ID |
| `mode` | string | 否 | 提取模式：`simple`、`normal`（默认）、`advanced` |
| `options` | object | 否 | 提取选项 |

**options 参数：**

| 参数 | 类型 | 说明 |
|-----|------|------|
| `language` | string | 文档语言：`zh`、`en`、`ja`、`ko` |
| `ocr_provider` | string | OCR 提供者：`default`、`tesseract`、`cloud` |
| `extract_tables` | boolean | 是否提取表格（默认 true） |
| `preserve_layout` | boolean | 是否保留排版（默认 false） |

### 示例

```bash
curl -X POST https://api.unifiles.dev/v1/extractions \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "file_abc123",
    "mode": "normal",
    "options": {"language": "zh"}
  }'
```

### 响应

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "pending",
    "mode": "normal",
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 400 | `INVALID_FILE_ID` | 文件 ID 无效 |
| 404 | `FILE_NOT_FOUND` | 文件不存在 |
| 415 | `UNSUPPORTED_FORMAT` | 不支持的文件格式 |

---

## 获取提取状态/结果

获取提取任务的状态和结果。

```http
GET /v1/extractions/{extraction_id}
```

### 路径参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `extraction_id` | string | 提取任务 ID |

### 示例

```bash
curl -X GET https://api.unifiles.dev/v1/extractions/ext_xyz789 \
  -H "Authorization: Bearer <api-key>"
```

### 响应（处理中）

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "processing",
    "mode": "normal",
    "progress": 45,
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 响应（完成）

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "completed",
    "mode": "normal",
    "markdown": "# 文档标题\n\n这是提取的内容...",
    "total_pages": 15,
    "metadata": {
        "title": "文档标题",
        "author": "作者名",
        "created_date": "2024-01-01"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:31:30Z"
}
```

### 响应（失败）

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "failed",
    "mode": "normal",
    "error": {
        "code": "OCR_FAILED",
        "message": "OCR 识别失败"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:31:30Z"
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|-------|-------|------|
| 404 | `EXTRACTION_NOT_FOUND` | 提取任务不存在 |

---

## 获取文件的提取记录

获取指定文件的所有提取记录。

```http
GET /v1/files/{file_id}/extractions
```

### 路径参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `file_id` | string | 文件 ID |

### 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `limit` | integer | 50 | 每页数量 |
| `offset` | integer | 0 | 偏移量 |

### 示例

```bash
curl -X GET https://api.unifiles.dev/v1/files/file_abc123/extractions \
  -H "Authorization: Bearer <api-key>"
```

### 响应

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "items": [
        {
            "id": "ext_xyz789",
            "status": "completed",
            "mode": "normal",
            "total_pages": 15,
            "created_at": "2024-01-15T10:30:00Z"
        },
        {
            "id": "ext_abc456",
            "status": "completed",
            "mode": "advanced",
            "total_pages": 15,
            "created_at": "2024-01-14T09:00:00Z"
        }
    ],
    "total": 2
}
```

---

## Extraction 对象

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 提取任务唯一标识 |
| `file_id` | string | 关联的文件 ID |
| `status` | string | 状态：`pending`、`processing`、`completed`、`failed` |
| `mode` | string | 提取模式 |
| `progress` | integer | 进度百分比（0-100） |
| `markdown` | string | 提取的 Markdown 内容（完成后） |
| `total_pages` | integer | 文档总页数 |
| `metadata` | object | 提取的文档元信息 |
| `error` | object | 错误信息（失败时） |
| `created_at` | string | 创建时间 |
| `completed_at` | string | 完成时间 |

## 提取模式说明

| 模式 | 说明 | 处理速度 | 适用场景 |
|-----|------|---------|---------|
| `simple` | 快速提取，不进行 OCR | 最快 | 纯文本文档 |
| `normal` | 标准提取，智能 OCR | 中等 | 大多数文档 |
| `advanced` | 高精度提取，完整 OCR | 较慢 | 扫描件、复杂排版 |
