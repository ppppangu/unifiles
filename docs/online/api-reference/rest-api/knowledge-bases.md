# Knowledge Bases API

知识库管理接口，提供知识库创建、文档管理和语义搜索功能。

!!! note
    下列资源响应片段只展示统一 envelope 中的 `data` 内容；完整格式见 REST API 概述。

## 创建知识库

```http
POST /v1/knowledge-bases
```

### 请求

```json
{
    "name": "legal-docs",
    "description": "法律文档知识库",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `name` | string | 是 | 知识库名称 |
| `description` | string | 否 | 描述 |
| `chunking_strategy` | object | 否 | 分块策略 |
| `metadata` | object | 否 | 自定义元数据 |

**chunking_strategy:**

| 参数 | 类型 | 说明 |
|-----|------|------|
| `type` | string | `fixed`、`semantic`、`paragraph` |
| `chunk_size` | integer | 分块大小（tokens） |
| `overlap` | integer | 重叠大小（tokens） |

### 响应

```http
HTTP/1.1 201 Created

{
    "id": "kb_abc123",
    "name": "legal-docs",
    "description": "法律文档知识库",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    },
    "document_count": 0,
    "chunk_count": 0,
    "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 列出知识库

```http
GET /v1/knowledge-bases
```

### 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `limit` | integer | 50 | 每页数量 |
| `offset` | integer | 0 | 偏移量 |

### 响应

```http
HTTP/1.1 200 OK

{
    "items": [
        {
            "id": "kb_abc123",
            "name": "legal-docs",
            "document_count": 42,
            "chunk_count": 1250,
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "total": 5
}
```

---

## 获取知识库详情

```http
GET /v1/knowledge-bases/{kb_id}
```

### 响应

```http
HTTP/1.1 200 OK

{
    "id": "kb_abc123",
    "name": "legal-docs",
    "description": "法律文档知识库",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    },
    "document_count": 42,
    "chunk_count": 1250,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-16T14:00:00Z"
}
```

---

## 更新知识库

```http
PATCH /v1/knowledge-bases/{kb_id}
```

### 请求

```json
{
    "name": "legal-docs-v2",
    "description": "更新后的描述"
}
```

### 响应

```http
HTTP/1.1 200 OK

{
    "id": "kb_abc123",
    "name": "legal-docs-v2",
    "description": "更新后的描述",
    ...
}
```

---

## 删除知识库

删除知识库及其所有文档和分块。

```http
DELETE /v1/knowledge-bases/{kb_id}
```

### 响应

```http
HTTP/1.1 204 No Content
```

---

## 添加文档

将已提取的文件添加到知识库。

```http
POST /v1/knowledge-bases/{kb_id}/documents
```

### 请求

```json
{
    "file_id": "file_xyz789",
    "title": "合同模板 v2.0",
    "metadata": {
        "category": "contract",
        "version": "2.0"
    }
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `file_id` | string | 是 | 文件 ID（须已完成提取） |
| `title` | string | 否 | 文档标题 |
| `metadata` | object | 否 | 自定义元数据 |

### 响应

```http
HTTP/1.1 201 Created

{
    "id": "doc_def456",
    "kb_id": "kb_abc123",
    "file_id": "file_xyz789",
    "title": "合同模板 v2.0",
    "status": "pending",
    "metadata": {
        "category": "contract",
        "version": "2.0"
    },
    "created_at": "2024-01-15T10:35:00Z"
}
```

---

## 列出文档

```http
GET /v1/knowledge-bases/{kb_id}/documents
```

### 响应

```http
HTTP/1.1 200 OK

{
    "items": [
        {
            "id": "doc_def456",
            "title": "合同模板 v2.0",
            "status": "indexed",
            "chunk_count": 42,
            "created_at": "2024-01-15T10:35:00Z"
        }
    ],
    "total": 42
}
```

---

## 获取文档详情

```http
GET /v1/knowledge-bases/{kb_id}/documents/{document_id}
```

### 响应

```http
HTTP/1.1 200 OK

{
    "id": "doc_def456",
    "kb_id": "kb_abc123",
    "file_id": "file_xyz789",
    "title": "合同模板 v2.0",
    "status": "indexed",
    "chunk_count": 42,
    "metadata": {
        "category": "contract"
    },
    "created_at": "2024-01-15T10:35:00Z",
    "indexed_at": "2024-01-15T10:36:00Z"
}
```

---

## 删除文档

```http
DELETE /v1/knowledge-bases/{kb_id}/documents/{document_id}
```

### 响应

```http
HTTP/1.1 204 No Content
```

---

## 语义搜索

```http
POST /v1/knowledge-bases/{kb_id}/search
```

### 请求

```json
{
    "query": "违约条款有哪些？",
    "top_k": 5,
    "threshold": 0.7,
    "filter": {
        "metadata.category": "contract"
    }
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `query` | string | 是 | 搜索查询 |
| `top_k` | integer | 否 | 返回数量（默认 5，最大 100） |
| `threshold` | float | 否 | 相似度阈值（0-1） |
| `filter` | object | 否 | 元数据过滤条件 |

### 响应

```http
HTTP/1.1 200 OK

{
    "query": "违约条款有哪些？",
    "chunks": [
        {
            "id": "chunk_001",
            "document_id": "doc_def456",
            "document_title": "合同模板 v2.0",
            "content": "第十条 违约责任\n\n1. 甲方违约...",
            "score": 0.92,
            "metadata": {
                "page": 5,
                "section": "第十条"
            }
        }
    ],
    "total": 1
}
```

---

## 混合搜索

结合语义搜索和关键词搜索。

```http
POST /v1/knowledge-bases/{kb_id}/hybrid-search
```

### 请求

```json
{
    "query": "违约金计算方法",
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "top_k": 10
}
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `query` | string | 是 | 搜索查询 |
| `vector_weight` | float | 否 | 语义搜索权重（默认 0.7） |
| `keyword_weight` | float | 否 | 关键词搜索权重（默认 0.3） |
| `top_k` | integer | 否 | 返回数量 |

### 响应

```http
HTTP/1.1 200 OK

{
    "query": "违约金计算方法",
    "chunks": [
        {
            "id": "chunk_002",
            "document_id": "doc_def456",
            "content": "违约金按合同金额的10%计算...",
            "score": 0.88,
            "vector_score": 0.85,
            "keyword_score": 0.95
        }
    ]
}
```

---

## 对象定义

### Knowledge Base

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 知识库 ID |
| `name` | string | 名称 |
| `description` | string | 描述 |
| `chunking_strategy` | object | 分块策略 |
| `document_count` | integer | 文档数量 |
| `chunk_count` | integer | 分块数量 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### Document

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 文档 ID |
| `kb_id` | string | 所属知识库 ID |
| `file_id` | string | 关联文件 ID |
| `title` | string | 标题 |
| `status` | string | `pending`、`indexing`、`indexed`、`failed` |
| `chunk_count` | integer | 分块数量 |
| `metadata` | object | 元数据 |

### Chunk

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | string | 分块 ID |
| `document_id` | string | 所属文档 ID |
| `document_title` | string | 文档标题 |
| `content` | string | 分块内容 |
| `score` | float | 相似度分数 |
| `metadata` | object | 元数据 |
