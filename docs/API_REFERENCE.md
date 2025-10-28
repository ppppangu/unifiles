# Unifiles v1 API 参考文档

## 概述

Unifiles v1 提供RESTful API，用于企业级文件存储、内容处理和知识库管理。本API采用三层架构设计（文件、处理、知识库），符合REST标准，支持Bearer Token认证。

### 基本信息

- **Base URL**: `http://localhost:8088`
- **API 版本**: v1.1.0
- **认证方式**: Bearer Token
- **数据格式**: JSON
- **交互式文档**: `http://localhost:8088/docs` (Swagger UI)

### 认证

所有API请求都需要在请求头中包含有效的Bearer Token：

```
Authorization: Bearer [REDACTED]
```

---

## 接口分类

### 系统接口 (System)

#### 1. 健康检查

**GET** `/health`

检查服务状态和基本信息。

**请求示例:**
```bash
curl -X GET "http://localhost:8088/health"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Service is healthy",
  "data": {
    "version": "1.1.0",
    "service": "file-server-v1"
  }
}
```

---

### 文件接口 (Files)

文件层负责文件的上传、下载和元数据管理。

#### 1. 获取支持的文件类型

**GET** `/files/types`

获取系统支持上传的所有文件类型。

**请求示例:**
```bash
curl -X GET "http://localhost:8088/files/types" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "document_types": [".doc", ".docx", ".ppt", "..."],
  "pdf_types": [".pdf"],
  "code_types": [".py", ".ipynb", ".js", ".json"],
  "all_types": [".doc", ".docx", ".pdf", ".py", "..."]
}
```

#### 2. 获取用户文件列表

**GET** `/files`

获取当前用户的所有文件列表，支持分页。

**查询参数 (可选):**
- `limit`: 返回数量限制 (默认: 50, 范围: 1-100)
- `offset`: 分页偏移量 (默认: 0)

**请求示例:**
```bash
curl -X GET "http://localhost:8088/files?limit=20&offset=0" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Files retrieved successfully",
  "files": [
    {
      "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "filename": "document.pdf",
      "file_size": 1024768,
      "content_type": "application/pdf",
      "public_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
      "object_path": "user-id/default_file_space/file-id/document.pdf",
      "created_at": "2024-09-12T10:30:00.123456"
    },
    {
      "file_id": "file-b2c3d4e5-f6g7-8901-bcde-f23456789012",
      "filename": "presentation.pptx",
      "file_size": 2048576,
      "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "public_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/presentation.pptx",
      "object_path": "user-id/default_file_space/file-id/presentation.pptx", 
      "created_at": "2024-09-12T09:15:00.987654"
    }
  ],
  "total_count": null,
  "has_more": true
}
```

#### 3. 上传文件

**POST** `/files`

上传单个文件到存储系统。

**请求参数:**
- `file`: 要上传的文件 (form-data)

**请求示例:**
```bash
curl -X POST "http://localhost:8088/files" \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@document.pdf"
```

**响应示例:**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "file": {
    "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "document.pdf",
    "file_size": 1024768,
    "content_type": "application/pdf",
    "public_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
    "object_path": "user-id/default_file_space/file-id/document.pdf",
    "created_at": "2024-09-12T10:30:00.123456"
  }
}
```

#### 4. 获取文件信息

**GET** `/files/{file_id}`

根据文件ID获取文件的详细信息。

**路径参数:**
- `file_id`: 文件唯一标识符

**请求示例:**
```bash
curl -X GET "http://localhost:8088/files/file-a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "document.pdf",
  "file_size": 1024768,
  "content_type": "application/pdf",
  "public_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
  "object_path": "user-id/default_file_space/file-id/document.pdf",
  "created_at": "2024-09-12T10:30:00.123456"
}
```

#### 5. 删除文件

**DELETE** `/files/{file_id}`

从存储系统中删除指定文件。只有文件所有者可以删除。

**路径参数:**
- `file_id`: 文件唯一标识符

**请求示例:**
```bash
curl -X DELETE "http://localhost:8088/files/file-a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "File deleted successfully",
  "data": {
    "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

---

### 处理接口 (Processors)

处理层负责对已上传的文件进行内容提取和分析。

#### 1. 提取文件内容

**POST** `/files/{file_id}/extract`

对指定文件执行内容提取，生成标准化的Markdown和元数据。这是将文件内容索引到知识库的前置步骤。

**路径参数:**
- `file_id`: 要处理的文件ID

**请求体参数:**
```json
{
  "mode": "mistral"
}
```
- `mode` (string): 提取模式，支持 `simple` (基础文本提取), `mistral` (Mistral OCR), `selfhosted`（自托管多模态OCR）。默认为 `simple`。

**请求示例:**
```bash
curl -X POST "http://localhost:8088/files/file-a1b2c3d4/extract" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"mode": "mistral"}'
```

**响应示例:**
```json
{
  "success": true,
  "message": "File content extraction started successfully",
  "document": {
    "file_id": "file-a1b2c3d4",
    "extraction_id": "extract-e8f7g6h5-i4j3-k2l1-m0n9-o8p7q6r5s4t3",
    "content_type": "text/markdown",
    "status": "processing",
    "extraction_metadata": {
      "engine": "core-processor-v1.1",
      "mode": "normal"
    },
    "created_at": "2024-09-12T11:00:00.567890"
  }
}
```
**状态:** 🚧 开发中 (核心逻辑待实现)

---

### 知识库接口 (Knowledge Bases)

知识库层负责将已处理的内容进行分块、向量化并存入知识库以供检索。

#### 1. 获取用户知识库列表

**GET** `/knowledge-bases`

获取当前用户的所有知识库列表，支持分页。

**查询参数 (可选):**
- `limit`: 返回数量限制 (默认: 50)
- `offset`: 分页偏移量 (默认: 0)

**请求示例:**
```bash
curl -X GET "http://localhost:8088/knowledge-bases?limit=20&offset=0" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Knowledge bases retrieved successfully",
  "knowledge_bases": [
    {
      "kb_id": "kb_sample_001",
      "name": "示例知识库",
      "description": "这是一个示例知识库",
      "user_id": "user-abc-123",
      "document_count": 5,
      "created_at": "2024-01-15T10:30:00.123456",
      "updated_at": "2024-01-15T15:45:00.123456"
    }
  ],
  "total_count": 1,
  "has_more": false
}
```
**状态:** 🚧 开发中 (返回示例数据)

#### 2. 获取知识库信息

**GET** `/knowledge-bases/{kb_id}`

获取指定知识库的基本信息和统计数据。

**路径参数:**
- `kb_id`: 知识库ID

**请求示例:**
```bash
curl -X GET "http://localhost:8088/knowledge-bases/my_knowledge_base" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "kb_id": "my_knowledge_base",
  "user_id": "user-abc-123",
  "document_count": 25,
  "created_at": "2024-01-15T10:30:00.123456",
  "updated_at": "2024-01-15T15:45:00.123456"
}
```
**状态:** 🚧 开发中 (501 Not Implemented)

#### 3. 索引内容到知识库

**POST** `/knowledge-bases/{kb_id}/documents`

将已提取的内容（通过`extraction_id`指定）进行分块和向量化，并索引到指定的知识库中。

**路径参数:**
- `kb_id`: 目标知识库ID

**请求体参数:**
```json
{
  "extraction_id": "extract-e8f7g6h5-i4j3-k2l1-m0n9-o8p7q6r5s4t3",
  "knowledge_base_id": "my_kb",
  "chunk_strategy": "semantic"
}
```

- `extraction_id` (string, required): 内容提取文件的ID。
- `knowledge_base_id` (string, required): 目标知识库ID。
- `chunk_strategy` (string): 分块策略，支持 `semantic` (语义分块), `fixed` (固定大小), `sliding` (滑动窗口)。默认为 `semantic`。

**请求示例:**

```bash
curl -X POST "http://localhost:8088/knowledge-bases/my_kb/documents" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d 
  '{ 
    "extraction_id": "extract-e8f7g6h5-i4j3-k2l1-m0n9-o8p7q6r5s4t3",
    "knowledge_base_id": "my_kb",
    "chunk_strategy": "semantic"
  }'
```

**响应示例:**
```json
{
  "success": true,
  "message": "Document indexing started successfully",
  "document": {
    "document_id": "doc_a1b2c3d4",
    "extraction_id": "extract-e8f7g6h5-i4j3-k2l1-m0n9-o8p7q6r5s4t3",
    "knowledge_base_id": "my_kb",
    "chunk_count": 0,
    "indexing_status": "processing",
    "created_at": "2024-09-12T11:05:00.123456"
  }
}
```
**状态:** 🚧 开发中 (501 Not Implemented)

#### 4. 获取知识库文档列表

**GET** `/knowledge-bases/{kb_id}/documents`

获取指定知识库中的所有已索引文档。

**路径参数:**
- `kb_id`: 知识库ID

**查询参数 (可选):**
- `limit`: 返回数量限制 (默认: 50)
- `offset`: 分页偏移量 (默认: 0)

**请求示例:**
```bash
curl -X GET "http://localhost:8088/knowledge-bases/my_kb/documents?limit=20" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
[
  {
    "document_id": "doc_a1b2c3d4",
    "extraction_id": "extract-e8f7g6h5-i4j3-k2l1-m0n9-o8p7q6r5s4t3",
    "knowledge_base_id": "my_kb",
    "chunk_count": 128,
    "indexing_status": "completed",
    "created_at": "2024-09-12T11:05:00.123456"
  }
]
```
**状态:** 🚧 开发中 (501 Not Implemented)

#### 5. 删除知识库文档

**DELETE** `/knowledge-bases/{kb_id}/documents/{doc_id}`

从知识库中删除指定文档及其所有分块和向量数据。

**路径参数:**
- `kb_id`: 知识库ID
- `doc_id`: 文档ID

**请求示例:**
```bash
curl -X DELETE "http://localhost:8088/knowledge-bases/my_kb/documents/doc_a1b2c3d4" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Document deleted successfully",
  "data": {
    "document_id": "doc_a1b2c3d4"
  }
}
```
**状态:** 🚧 开发中 (501 Not Implemented)

---

## 数据模型

### FileInfo
文件信息模型
```json
{
  "file_id": "string",
  "filename": "string",
  "file_size": 0,
  "content_type": "string",
  "public_url": "string",
  "object_path": "string",
  "created_at": "string"
}
```

### FileListResponse
文件列表响应模型
```json
{
  "success": true,
  "message": "string",
  "files": [
    {
      "file_id": "string",
      "filename": "string",
      "file_size": 0,
      "content_type": "string",
      "public_url": "string",
      "object_path": "string",
      "created_at": "string"
    }
  ],
  "total_count": 0,
  "has_more": true
}
```

### ExtractionFile
提取的文件信息模型
```json
{
  "file_id": "string",
  "extraction_id": "string",
  "content_type": "string",
  "status": "string",
  "extraction_metadata": {},
  "created_at": "string"
}
```

### ProcessedDocument
已处理（索引）的文档信息模型
```json
{
  "document_id": "string",
  "extraction_id": "string",
  "knowledge_base_id": "string",
  "chunk_count": 0,
  "indexing_status": "string",
  "created_at": "string"
}
```

### KnowledgeBaseInfo
知识库信息模型
```json
{
  "kb_id": "string",
  "name": "string",
  "description": "string",
  "user_id": "string",
  "document_count": 0,
  "created_at": "string",
  "updated_at": "string"
}
```

### KnowledgeBaseListResponse
知识库列表响应模型
```json
{
  "success": true,
  "message": "string",
  "knowledge_bases": [
    {
      "kb_id": "string",
      "name": "string", 
      "description": "string",
      "user_id": "string",
      "document_count": 0,
      "created_at": "string",
      "updated_at": "string"
    }
  ],
  "total_count": 0,
  "has_more": true
}
```

---

## 错误代码

| HTTP状态码 | 说明           |
| ---------- | -------------- |
| 200        | 请求成功       |
| 400        | 请求参数错误   |
| 401        | 认证失败       |
| 403        | 权限不足       |
| 404        | 资源不存在     |
| 500        | 服务器内部错误 |
| 501        | 功能未实现     |

---

## 开发状态

### ✅ 已实现接口框架

- 健康检查接口
- 文件管理 (上传/获取/删除)
- 内容提取接口
- 知识库文档管理 (索引/获取/删除)
- Bearer Token 认证

### 🚧 待实现核心逻辑

- **内容提取**: `simple`, `normal`, 模式的实际处理逻辑。
- **知识库索引**: 文档分块、向量化和存储的实际逻辑。
- **数据库持久化**: 所有 `501 Not Implemented` 接口的数据库操作。

---

## 更多信息

- **API交互式文档**: http://localhost:8088/docs
- **ReDoc文档**: http://localhost:8088/redoc
- **架构设计**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **快速开始指南**: [QUICK_START.md](QUICK_START.md)
- **开发指南**: [DEVELOPMENT.md](DEVELOPMENT.md)
