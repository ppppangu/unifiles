# Unifiles API 端点文档

本文档提供所有可用 API 端点的完整参考，包括请求格式和响应示例。

**基础 URL**: `http://localhost:8088`

**认证方式**: 大部分端点需要通过 `Authorization: Bearer <token>` 提供访问密钥，`AuthMiddleware` 会自动验证并将 `user_id` 注入到 `request.state`。

---

## 目录

1. [系统端点](#系统端点)
2. [用户管理 (/users)](#用户管理-users)
3. [文件管理 (/files)](#文件管理-files)
4. [内容提取 (/files/{file_id}/extract)](#内容提取-filesfile_idextract)
5. [知识库管理 (/knowledge-bases)](#知识库管理-knowledge-bases)
6. [管理员端点 (/manager)](#管理员端点-manager)

---

## 系统端点

### GET /health

系统健康检查端点（无需认证）

**请求示例**:
```bash
curl -X GET "http://localhost:8088/health"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Service is healthy",
  "data": {
    "version": "1.1.0",
    "service": "unifiles-v1"
  }
}
```

---

## 用户管理 (/users)

### POST /users/create

创建新用户（无需认证）

**请求体**:
```json
{
  "user_id": "user_123",
  "username": "john_doe",
  "email": "john@example.com",
  "display_name": "John Doe",
  "user_settings": {}
}
```

**请求示例**:
```bash
curl -X POST "http://localhost:8088/users/create" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe"
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "User created successfully",
  "user": {
    "id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2025-10-23T10:00:00",
    "updated_at": "2025-10-23T10:00:00",
    "last_login_at": null
  }
}
```

**错误响应**:
- `409 Conflict`: 用户已存在
- `500 Internal Server Error`: 创建失败

---

### GET /users/{user_id}

获取用户信息（无需认证）

**路径参数**:
- `user_id` (string): 用户ID

**请求示例**:
```bash
curl -X GET "http://localhost:8088/users/user_123"
```

**响应示例**:
```json
{
  "success": true,
  "message": "User retrieved successfully",
  "data": {
    "id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2025-10-23T10:00:00",
    "updated_at": "2025-10-23T10:00:00",
    "last_login_at": null
  }
}
```

**错误响应**:
- `404 Not Found`: 用户不存在

---

### POST /users/login

用户登录 - 通过邮箱获取用户信息（无需认证）

**查询参数**:
- `email` (string): 用户邮箱

**请求示例**:
```bash
curl -X POST "http://localhost:8088/users/login?email=john@example.com"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2025-10-23T10:00:00",
    "updated_at": "2025-10-23T10:00:00",
    "last_login_at": "2025-10-23T10:00:00"
  }
}
```

**错误响应**:
- `404 Not Found`: 邮箱对应的用户不存在

---

### POST /users/{user_id}/access-keys

为指定用户创建访问密钥（API Key）

**路径参数**:
- `user_id` (string): 用户ID

**请求体**:
```json
{
  "name": "My API Key",
  "description": "Used for production access",
  "scopes": ["read", "write"],
  "expires_at": "2026-10-23T10:00:00"
}
```

**请求示例**:
```bash
curl -X POST "http://localhost:8088/users/user_123/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "description": "Used for production access",
    "scopes": ["read", "write"]
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "Access key created successfully",
  "key_id": "key_abc123",
  "access_key": "[REDACTED]xxxxxxxxxxxxxxxxx"
}
```

**注意**: `access_key` 仅在创建时返回一次，请妥善保存。

**错误响应**:
- `404 Not Found`: 用户不存在

---

### GET /users/{user_id}/access-keys

获取用户的访问密钥列表

**路径参数**:
- `user_id` (string): 用户ID

**查询参数**:
- `active` (boolean, 可选): 是否仅返回活跃密钥

**请求示例**:
```bash
curl -X GET "http://localhost:8088/users/user_123/access-keys?active=true"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Access keys retrieved successfully",
  "access_keys": [
    {
      "id": "key_abc123",
      "name": "My API Key",
      "description": "Used for production access",
      "scopes": ["read", "write"],
      "is_active": true,
      "created_at": "2025-10-23T10:00:00",
      "expires_at": "2026-10-23T10:00:00",
      "last_used_at": "2025-10-23T12:30:00"
    }
  ]
}
```

---

### DELETE /users/{user_id}/access-keys/{key_id} (目前不可用无需测试)

删除（撤销）指定用户的访问密钥

**路径参数**:
- `user_id` (string): 用户ID
- `key_id` (string): 访问密钥ID

**请求示例**:
```bash
curl -X DELETE "http://localhost:8088/users/user_123/access-keys/key_abc123"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Access key deleted successfully",
  "data": {
    "key_id": "key_abc123"
  }
}
```

**错误响应**:
- `404 Not Found`: 用户或密钥不存在
- `403 Forbidden`: 密钥不属于该用户

---

## 文件管理 (/files)

### GET /files/types

获取支持的文件类型（无需认证）

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/types"
```

**响应示例**:
```json
{
  "document_types": [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".ods", ".odp", ".txt", ".rtf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".html", ".htm", ".md", ".csv", ".tsv", ".xml"],
  "pdf_types": [".pdf"],
  "code_types": [".py", ".ipynb", ".js", ".json"],
  "all_types": ["...(所有支持的类型)"]
}
```

---

### POST /files

上传文件到存储（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**表单参数**:
- `file` (file): 要上传的文件
- `is_public` (boolean, 可选): 是否设置为公开访问，默认 false

**请求示例**:
```bash
curl -X POST "http://localhost:8088/files?is_public=false" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -F "file=@/path/to/document.pdf"
```

**响应示例**:
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "file": {
    "file_id": "file_xyz789",
    "filename": "document.pdf",
    "original_filename": "document.pdf",
    "file_type": "application/pdf",
    "file_size": 1048576,
    "user_id": "user_123",
    "storage_path": "user_123/file_xyz789.pdf",
    "is_public": false,
    "upload_status": "completed",
    "created_at": "2025-10-23T10:00:00",
    "updated_at": "2025-10-23T10:00:00"
  }
}
```

**错误响应**:
- `401 Unauthorized`: 缺少或无效的 Bearer Token
- `413 Payload Too Large`: 文件大小超过限制
- `415 Unsupported Media Type`: 不支持的文件类型

---

### GET /files

获取当前用户的文件列表（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**查询参数**:
- `limit` (integer, 可选): 返回数量限制，默认 50，最大 100
- `offset` (integer, 可选): 分页偏移量，默认 0

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files?limit=10&offset=0" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Files retrieved successfully",
  "files": [
    {
      "file_id": "file_xyz789",
      "filename": "document.pdf",
      "file_type": "application/pdf",
      "file_size": 1048576,
      "is_public": false,
      "created_at": "2025-10-23T10:00:00"
    }
  ],
  "total_count": 42,
  "has_more": true
}
```

---

### GET /files/{file_id}

获取文件信息（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `file_id` (string): 文件ID

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/file_xyz789" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "file_id": "file_xyz789",
  "filename": "document.pdf",
  "original_filename": "document.pdf",
  "file_type": "application/pdf",
  "file_size": 1048576,
  "user_id": "user_123",
  "storage_path": "user_123/file_xyz789.pdf",
  "is_public": false,
  "upload_status": "completed",
  "created_at": "2025-10-23T10:00:00",
  "updated_at": "2025-10-23T10:00:00"
}
```

**错误响应**:
- `404 Not Found`: 文件不存在或无权访问

---

### GET /files/public/{file_id}

获取公共文件信息（无需认证）

**路径参数**:
- `file_id` (string): 文件ID

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/public/file_xyz789"
```

**响应示例**: 同 `GET /files/{file_id}`

**错误响应**:
- `404 Not Found`: 文件不存在或未设为公开

---

### PATCH /files/{file_id}/public-status

更新文件的公开访问状态（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `file_id` (string): 文件ID

**查询参数**:
- `is_public` (boolean): 是否设置为公开访问

**请求示例**:
```bash
curl -X PATCH "http://localhost:8088/files/file_xyz789/public-status?is_public=true" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "message": "File public status updated to: true",
  "data": {
    "file_id": "file_xyz789",
    "is_public": true
  }
}
```

---

### DELETE /files/{file_id}

删除文件（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `file_id` (string): 文件ID

**请求示例**:
```bash
curl -X DELETE "http://localhost:8088/files/file_xyz789" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "message": "File deleted successfully",
  "data": {
    "file_id": "file_xyz789",
    "deleted_at": "2025-10-23T10:30:00"
  }
}
```

---

### GET /files/user/stats

获取用户存储统计信息（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/user/stats" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total_files": 42,
    "total_size_bytes": 104857600,
    "public_files": 5,
    "private_files": 37
  },
  "message": "Storage statistics retrieved successfully"
}
```

---

### GET /files/admin/health

获取存储后端健康状态（管理员功能，需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 管理员的访问密钥

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/admin/health" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "storage_backend": "minio",
  "status": "healthy",
  "buckets": ["unifiles-storage"],
  "connection": "active"
}
```

---

### GET /files/admin/metrics

获取存储指标（管理员功能，需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 管理员的访问密钥

**请求示例**:
```bash
curl -X GET "http://localhost:8088/files/admin/metrics" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "total_files": 1000,
  "total_size_bytes": 10485760000,
  "files_by_type": {
    "pdf": 450,
    "docx": 300,
    "image": 250
  }
}
```

---

## 内容提取 (/files/{file_id}/extract)

### POST /files/{file_id}/extract

提取文件内容（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `file_id` (string): 文件ID

**请求体**:
```json
{
  "mode": "mistral"
}
```

**mode 可选值**:
- `simple`: 使用 pdfplumber 进行基础文本提取
- `mistral`: 使用 Mistral OCR 进行多模态提取
- `mineru`: 使用 Mineru 进行多模态提取
- `selfhosted`: 使用自托管的多模态模型进行提取

**请求示例**:
```bash
curl -X POST "http://localhost:8088/files/file_xyz789/extract" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"mode": "mistral"}'
```

**响应示例**:
```json
{
  "success": true,
  "message": "File content extracted successfully",
  "extracted_content": {
    "file_id": "file_xyz789",
    "extraction_id": "extract_abc123",
    "content_type": "application/pdf",
    "extracted_text": "Full text content...",
    "markdown_content": "# Document Title\n\nContent in markdown...",
    "structured_data": {
      "pages": 10,
      "images": 5,
      "tables": 2
    },
    "extraction_metadata": {
      "mode": "mistral",
      "processed_at": "2025-10-23T10:05:00"
    },
    "extraction_strategy": "OCR-mistral",
    "status": "completed",
    "created_at": "2025-10-23T10:05:00"
  }
}
```

**错误响应**:
- `404 Not Found`: 文件不存在
- `403 Forbidden`: 权限不足
- `500 Internal Server Error`: 提取失败

---

## 知识库管理 (/knowledge-bases)

### POST /knowledge-bases

创建新的知识库（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**请求体**:
```json
{
  "name": "My Knowledge Base",
  "description": "A collection of technical documents"
}
```

**请求示例**:
```bash
curl -X POST "http://localhost:8088/knowledge-bases" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Knowledge Base",
    "description": "A collection of technical documents"
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "Knowledge base created successfully",
  "knowledge_base": {
    "kb_id": "kb_def456",
    "name": "My Knowledge Base",
    "description": "A collection of technical documents",
    "user_id": "user_123",
    "document_count": 0,
    "created_at": "2025-10-23T10:00:00",
    "updated_at": "2025-10-23T10:00:00"
  }
}
```

**错误响应**:
- `400 Bad Request`: 知识库名称为空
- `409 Conflict`: 知识库ID冲突

---

### GET /knowledge-bases

获取用户的知识库列表（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**查询参数**:
- `limit` (integer, 可选): 返回数量限制，默认 50
- `offset` (integer, 可选): 分页偏移量，默认 0

**请求示例**:
```bash
curl -X GET "http://localhost:8088/knowledge-bases?limit=10&offset=0" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "message": "Knowledge bases retrieved successfully",
  "knowledge_bases": [
    {
      "kb_id": "kb_def456",
      "name": "My Knowledge Base",
      "description": "A collection of technical documents",
      "user_id": "user_123",
      "document_count": 15,
      "created_at": "2025-10-23T10:00:00",
      "updated_at": "2025-10-23T11:00:00"
    }
  ],
  "total_count": 5,
  "has_more": false
}
```

---

### GET /knowledge-bases/{kb_id}

获取知识库信息（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `kb_id` (string): 知识库ID

**请求示例**:
```bash
curl -X GET "http://localhost:8088/knowledge-bases/kb_def456" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**状态**: `501 Not Implemented` (待实现)

---

### POST /knowledge-bases/{kb_id}/documents

将已提取的内容索引到知识库（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `kb_id` (string): 知识库ID

**请求体**:
```json
{
  "extraction_id": "extract_abc123",
  "chunk_strategy": "fixed_size"
}
```

**chunk_strategy 可选值**:
- `fixed_size`: 固定大小分块
- `semantic`: 语义分块
- `recursive`: 递归分块

**请求示例**:
```bash
curl -X POST "http://localhost:8088/knowledge-bases/kb_def456/documents" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "extraction_id": "extract_abc123",
    "chunk_strategy": "fixed_size"
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "Document indexed successfully to knowledge base",
  "document": {
    "document_id": "doc_ghi789",
    "extraction_id": "extract_abc123",
    "knowledge_base_id": "kb_def456",
    "chunk_count": 25,
    "indexing_status": "completed",
    "created_at": "2025-10-23T10:10:00"
  }
}
```

**错误响应**:
- `404 Not Found`: 知识库或提取文档不存在
- `403 Forbidden`: 权限不足
- `500 Internal Server Error`: 索引失败

---

### GET /knowledge-bases/{kb_id}/documents

获取知识库文档列表（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `kb_id` (string): 知识库ID

**查询参数**:
- `limit` (integer, 可选): 返回数量限制，默认 50
- `offset` (integer, 可选): 分页偏移量，默认 0

**请求示例**:
```bash
curl -X GET "http://localhost:8088/knowledge-bases/kb_def456/documents?limit=10&offset=0" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**状态**: `501 Not Implemented` (待实现)

---

### DELETE /knowledge-bases/{kb_id}/documents/{doc_id}

删除知识库文档（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `kb_id` (string): 知识库ID
- `doc_id` (string): 文档ID

**请求示例**:
```bash
curl -X DELETE "http://localhost:8088/knowledge-bases/kb_def456/documents/doc_ghi789" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx"
```

**状态**: `501 Not Implemented` (待实现)

---

### POST /knowledge-bases/{kb_id}/search

在知识库中进行向量检索（需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 用户的访问密钥

**路径参数**:
- `kb_id` (string): 知识库ID

**请求体**:
```json
{
  "query": "检索查询文本",
  "top_k": 10
}
```

**参数说明**:
- `query` (string, 必需): 检索查询文本，最少1个字符
- `top_k` (integer, 可选): 返回结果数量，默认10，范围1-100

**请求示例**:
```bash
curl -X POST "http://localhost:8088/knowledge-bases/kb_def456/search" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "电气自动化设备安装",
    "top_k": 5
  }'
```

**响应示例**:
```json
{
  "success": true,
  "message": "Found 4 results",
  "results": [
    {
      "chunk_id": "chunk_abc123",
      "component_id": "comp_def456",
      "document_id": "doc_ghi789",
      "text_content": "电气自动化设备安装与维修专业中...",
      "similarity_score": 0.85
    },
    {
      "chunk_id": "chunk_xyz789",
      "component_id": "comp_uvw456",
      "document_id": "doc_ghi789",
      "text_content": "如何通过项目式教学提升电气自动化设备...",
      "similarity_score": 0.72
    }
  ],
  "total_results": 4,
  "query": "电气自动化设备安装"
}
```

**响应字段说明**:
- `success` (boolean): 是否成功
- `message` (string): 响应消息
- `results` (array): 检索结果列表
  - `chunk_id` (string): 文本块ID
  - `component_id` (string): 组件ID
  - `document_id` (string): 文档ID
  - `text_content` (string): 文本内容
  - `similarity_score` (float): 相似度分数（0-1，越大越相似）
- `total_results` (integer): 返回结果数量
- `query` (string): 原始查询文本

**工作原理**:
1. 将查询文本转换为向量表示（使用嵌入模型）
2. 在知识库的所有文本块中进行向量相似度计算
3. 返回相似度最高的top_k个结果
4. 结果按相似度从高到低排序

**错误响应**:
- `400 Bad Request`: 查询参数无效（如query为空或top_k超出范围）
- `403 Forbidden`: 无权访问该知识库
- `404 Not Found`: 知识库不存在
- `500 Internal Server Error`: 检索失败

**性能说明**:
- 使用pgvector扩展进行高效向量检索
- 支持余弦相似度计算
- 建议知识库创建向量索引以优化查询性能

---

## 管理员端点 (/manager)

### GET /manager/system/status

获取系统状态信息（管理员专用，需要认证）

**请求头**:
- `Authorization: Bearer <token>`: 管理员的访问密钥

**请求示例**:
```bash
curl -X GET "http://localhost:8088/manager/system/status" \
  -H "Authorization: Bearer sk_admin_xxxxxxxxxxxxxxxxxxxx"
```

**响应示例**:
```json
{
  "success": true,
  "message": "System status retrieved successfully",
  "data": {
    "status": "healthy",
    "timestamp": "2025-10-23T10:00:00",
    "components": {
      "database": "connected",
      "storage": "healthy",
      "memory_usage": "normal",
      "disk_usage": "normal"
    }
  }
}
```

---

## 错误响应格式

所有错误响应遵循统一的格式：

```json
{
  "detail": "Error message describing what went wrong"
}
```

### 常见 HTTP 状态码

- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未授权（缺少或无效的 Bearer Token）
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突
- `413 Payload Too Large`: 请求体过大
- `415 Unsupported Media Type`: 不支持的媒体类型
- `500 Internal Server Error`: 服务器内部错误
- `501 Not Implemented`: 功能未实现
- `503 Service Unavailable`: 服务不可用（通常是数据库问题）

---

## 使用流程示例

### 完整工作流：从文件上传到知识库检索

```bash
# 1. 创建用户（如果还没有）
curl -X POST "http://localhost:8088/users/create" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe"
  }'

# 2. 创建访问密钥
curl -X POST "http://localhost:8088/users/user_123/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "scopes": ["read", "write"]
  }'
# 保存返回的 access_key

# 3. 上传文件
curl -X POST "http://localhost:8088/files" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -F "file=@document.pdf"
# 保存返回的 file_id

# 4. 提取文件内容
curl -X POST "http://localhost:8088/files/file_xyz789/extract" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"mode": "simple"}'
# 保存返回的 extraction_id

# 5. 创建知识库
curl -X POST "http://localhost:8088/knowledge-bases" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Knowledge Base",
    "description": "Technical documentation"
  }'
# 保存返回的 kb_id

# 6. 将提取的内容索引到知识库
curl -X POST "http://localhost:8088/knowledge-bases/kb_def456/documents" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "extraction_id": "extract_abc123",
    "chunk_strategy": "fixed_size"
  }'

# 7. 在知识库中进行向量检索
curl -X POST "http://localhost:8088/knowledge-bases/kb_def456/search" \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何安装电气设备",
    "top_k": 5
  }'
```

---

## 注意事项

1. **认证**: 除了标注"无需认证"的端点外，所有端点都需要在请求头中提供 `Authorization: Bearer <token>`
2. **访问密钥**: 创建访问密钥后，完整的密钥值仅返回一次，请妥善保存
3. **文件大小限制**: 上传文件时请注意文件大小限制（具体限制见配置）
4. **OCR 模式**: 不同的 OCR 模式有不同的性能和准确度特点，请根据需求选择
5. **数据流**: 文件 → 提取内容 → 知识库文档 → 向量检索，遵循"提取一次，多次使用"的设计原则
6. **分页**: 列表类端点支持分页，使用 `limit` 和 `offset` 参数
7. **未实现功能**: 标记为 `501 Not Implemented` 的端点正在开发中
8. **向量检索**:
   - 需要先将文档索引到知识库后才能进行检索
   - 检索性能依赖于向量索引（建议运行 `SELECT unifiles.create_embedding_index();`）
   - 相似度分数范围为0-1，值越大表示越相似
   - 支持中英文混合检索

---

## 更新日志

- **2025-10-23**:
  - 初始版本，覆盖所有现有端点
  - 新增知识库向量检索端点 `POST /knowledge-bases/{kb_id}/search`
  - 更新完整工作流示例，包含检索步骤
