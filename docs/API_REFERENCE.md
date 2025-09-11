# File Server v1 API 参考文档

## 概述

File Server v1 提供RESTful API，用于企业级文件存储、管理和知识库文档处理。本API符合REST架构标准，支持Bearer Token认证和数据库行级安全控制。

### 基本信息

- **Base URL**: `http://localhost:8088`
- **API 版本**: v1.0.0
- **认证方式**: Bearer Token
- **数据格式**: JSON
- **文档地址**: `http://localhost:8088/docs` (Swagger UI)

### 认证

所有API请求都需要在请求头中包含Bearer Token：

```
Authorization: Bearer [REDACTED]
```

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
    "version": "1.0.0",
    "service": "file-server-v1"
  }
}
```

---

### 文件管理接口 (Files)

#### 1. 获取支持的文件类型

**GET** `/files/types`

获取系统支持的所有文件类型。

**请求示例:**
```bash
curl -X GET "http://localhost:8088/files/types" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "document_types": [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".ods", ".odp", ".txt", ".rtf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".html", ".htm", ".md", ".csv", ".tsv", ".xml"],
  "pdf_types": [".pdf"],
  "code_types": [".py", ".ipynb", ".js", ".json"],
  "all_types": [".doc", ".docx", "..."]
}
```

#### 2. 上传文件

**POST** `/files`

上传文件到存储系统。文件会自动经过验证中间件检测。

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
    "created_at": "2024-01-15T10:30:00.123456"
  }
}
```

**错误响应:**
```json
{
  "detail": "Unsupported file type: .exe. Supported types: ['.pdf', '.doc', ...]"
}
```

#### 3. 获取文件信息

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
  "created_at": "2024-01-15T10:30:00.123456"
}
```

**错误响应:**
```json
{
  "detail": "File not found: file-invalid-id"
}
```

#### 4. 删除文件

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

**错误响应:**
```json
{
  "detail": "Access denied: file belongs to another user"
}
```

---

### 知识库接口 (Knowledge Bases)

#### 1. 创建知识库

**POST** `/knowledge-bases`

创建新的知识库。

**请求体参数:**
```json
{
  "kb_id": "my_knowledge_base",     // 知识库ID (唯一标识)
  "name": "我的知识库",              // 知识库名称
  "description": "用于存储技术文档的知识库"  // 描述 (可选)
}
```

**请求示例:**
```bash
curl -X POST "http://localhost:8088/knowledge-bases" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "tech_docs",
    "name": "技术文档库",
    "description": "存储所有技术相关文档"
  }'
```

**响应示例:**
```json
{
  "success": true,
  "message": "Knowledge base created successfully",
  "data": {
    "kb_id": "tech_docs",
    "name": "技术文档库",
    "description": "存储所有技术相关文档",
    "document_count": 0,
    "created_at": "2024-01-15T10:30:00.123456"
  }
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 2. 获取知识库列表

**GET** `/knowledge-bases`

获取当前用户的所有知识库列表。

**查询参数:**
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
  "data": {
    "knowledge_bases": [
      {
        "kb_id": "tech_docs",
        "name": "技术文档库",
        "description": "存储所有技术相关文档",
        "document_count": 15,
        "processing_count": 2,
        "completed_count": 13,
        "failed_count": 0,
        "created_at": "2024-01-15T10:30:00.123456",
        "updated_at": "2024-01-15T15:45:00.123456"
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 3. 获取知识库信息

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
  "success": true,
  "message": "Knowledge base retrieved successfully",
  "data": {
    "kb_id": "my_knowledge_base",
    "name": "我的知识库",
    "description": "用于存储技术文档的知识库",
    "document_count": 25,
    "processing_count": 3,
    "completed_count": 20,
    "failed_count": 2,
    "total_size": 10485760,
    "created_at": "2024-01-15T10:30:00.123456",
    "updated_at": "2024-01-15T15:45:00.123456"
  }
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 4. 删除知识库

**DELETE** `/knowledge-bases/{kb_id}`

删除指定的知识库及其所有文档和向量数据。

**路径参数:**
- `kb_id`: 知识库ID

**请求示例:**
```bash
curl -X DELETE "http://localhost:8088/knowledge-bases/tech_docs" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Knowledge base deleted successfully",
  "data": {
    "kb_id": "tech_docs",
    "deleted_documents": 15
  }
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 5. 处理文档到知识库

**POST** `/knowledge-bases/{kb_id}/documents`

将文档处理并添加到知识库。支持两种方式：处理已存储文件或外部URL文件。

**路径参数:**
- `kb_id`: 知识库ID

**请求体参数:**
```json
{
  "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",  // 可选：已存储文件ID
  "file_url": "https://example.com/document.pdf",          // 可选：外部文件URL
  "mode": "simple"                                         // 处理模式: simple|normal
}
```

**注意:** `file_id` 和 `file_url` 必须提供其中一个，且不能同时提供。

**请求示例:**
```bash
# 方式1：处理已存储的文件
curl -X POST "http://localhost:8088/knowledge-bases/my_kb/documents" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "mode": "simple"
  }'

# 方式2：处理外部URL文件 (开发中)
curl -X POST "http://localhost:8088/knowledge-bases/my_kb/documents" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/document.pdf",
    "mode": "normal"
  }'
```

**响应示例:**
```json
{
  "success": true,
  "message": "Document processing started successfully",
  "document": {
    "document_id": "doc_a1b2c3d4",
    "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "original_file_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
    "markdown_url": null,
    "pdf_url": null,
    "mode": "simple",
    "status": "processing",
    "knowledge_base_id": "my_kb",
    "created_at": "2024-01-15T10:35:00.123456"
  }
}
```

**错误响应:**
```json
{
  "detail": "Either file_id or file_url must be provided"
}
```

#### 6. 获取知识库文档列表

**GET** `/knowledge-bases/{kb_id}/documents`

获取指定知识库中的所有文档。按你的要求，基本盘是全部获取，后续可添加可选参数。

**路径参数:**
- `kb_id`: 知识库ID

**查询参数 (可选):**
- `limit`: 返回文档数量限制 (默认: 50)
- `offset`: 分页偏移量 (默认: 0)
- `status`: 按状态筛选 (`processing`, `completed`, `failed`)
- `sort_by`: 排序字段 (`created_at`, `filename`, `file_size`) (默认: `created_at`)
- `sort_order`: 排序方式 (`asc`, `desc`) (默认: `desc`)

**请求示例:**
```bash
# 基本请求 - 获取全部文档
curl -X GET "http://localhost:8088/knowledge-bases/my_kb/documents" \
  -H "Authorization: Bearer [REDACTED]"

# 带筛选条件的请求
curl -X GET "http://localhost:8088/knowledge-bases/my_kb/documents?status=completed&limit=20&offset=0" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Documents retrieved successfully",
  "data": {
    "documents": [
      {
        "document_id": "doc_a1b2c3d4",
        "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "filename": "技术文档.pdf",
        "file_size": 1024768,
        "content_type": "application/pdf",
        "original_file_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
        "markdown_url": "http://localhost:9000/bucket-name/user-id/processed_files/doc_a1b2c3d4.md",
        "pdf_url": "http://localhost:9000/bucket-name/user-id/processed_files/doc_a1b2c3d4.pdf",
        "mode": "simple",
        "status": "completed",
        "processing_progress": 100,
        "error_message": null,
        "knowledge_base_id": "my_kb",
        "created_at": "2024-01-15T10:35:00.123456",
        "completed_at": "2024-01-15T10:38:15.789123"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0,
    "status_counts": {
      "processing": 3,
      "completed": 20,
      "failed": 2
    }
  }
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 7. 获取文档详情

**GET** `/knowledge-bases/{kb_id}/documents/{doc_id}`

获取指定文档的详细信息和处理状态。

**路径参数:**
- `kb_id`: 知识库ID
- `doc_id`: 文档ID

**请求示例:**
```bash
curl -X GET "http://localhost:8088/knowledge-bases/my_kb/documents/doc_a1b2c3d4" \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Document retrieved successfully",
  "data": {
    "document_id": "doc_a1b2c3d4",
    "file_id": "file-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "技术文档.pdf",
    "file_size": 1024768,
    "content_type": "application/pdf",
    "original_file_url": "http://localhost:9000/bucket-name/user-id/default_file_space/file-id/document.pdf",
    "markdown_url": "http://localhost:9000/bucket-name/user-id/processed_files/doc_a1b2c3d4.md",
    "pdf_url": "http://localhost:9000/bucket-name/user-id/processed_files/doc_a1b2c3d4.pdf",
    "mode": "simple",
    "status": "completed",
    "processing_progress": 100,
    "processing_logs": [
      {
        "timestamp": "2024-01-15T10:35:05.123",
        "level": "INFO",
        "message": "开始处理文档"
      },
      {
        "timestamp": "2024-01-15T10:38:15.789",
        "level": "INFO", 
        "message": "文档处理完成"
      }
    ],
    "error_message": null,
    "knowledge_base_id": "my_kb",
    "created_at": "2024-01-15T10:35:00.123456",
    "completed_at": "2024-01-15T10:38:15.789123"
  }
}
```

**错误响应:**
```json
{
  "detail": "Document not found in knowledge base"
}
```

**状态:** 🚧 开发中 (501 Not Implemented)

#### 8. 删除知识库文档

**DELETE** `/knowledge-bases/{kb_id}/documents/{doc_id}`

从知识库中删除指定文档及其向量数据。

**路径参数:**
- `kb_id`: 知识库ID
- `doc_id`: 文档ID

**请求示例:**
```bash
curl -X DELETE "http://localhost:8088/knowledge-bases/my_kb/documents/doc_a1b2c3d4" \
  -H "Authorization: Bearer [REDACTED]"
```

**状态:** 🚧 开发中 (501 Not Implemented)

---

## 数据模型

### FileInfo - 文件信息

```json
{
  "file_id": "string",       // 文件唯一标识
  "filename": "string",      // 原始文件名
  "file_size": 0,           // 文件大小（字节）
  "content_type": "string",  // 文件MIME类型
  "public_url": "string",    // 公网访问URL
  "object_path": "string",   // 存储路径
  "created_at": "string"     // 上传时间 (ISO 8601)
}
```

### KnowledgeBase - 知识库信息

```json
{
  "kb_id": "string",            // 知识库ID
  "name": "string",             // 知识库名称
  "description": "string",      // 描述 (可选)
  "document_count": 0,          // 总文档数
  "processing_count": 0,        // 处理中文档数
  "completed_count": 0,         // 已完成文档数
  "failed_count": 0,            // 失败文档数
  "total_size": 0,             // 总大小（字节）
  "created_at": "string",       // 创建时间 (ISO 8601)
  "updated_at": "string"        // 更新时间 (ISO 8601)
}
```

### ProcessedDocument - 已处理文档

```json
{
  "document_id": "string",        // 文档ID
  "file_id": "string",           // 文件ID
  "filename": "string",          // 原始文件名
  "file_size": 0,               // 文件大小（字节）
  "content_type": "string",      // 文件MIME类型
  "original_file_url": "string", // 原始文件URL
  "markdown_url": "string",      // Markdown文件URL (可选)
  "pdf_url": "string",          // PDF文件URL (可选)
  "mode": "string",             // 处理模式
  "status": "string",           // 处理状态 (processing, completed, failed)
  "processing_progress": 0,      // 处理进度 (0-100)
  "processing_logs": [],        // 处理日志 (可选)
  "error_message": "string",     // 错误信息 (可选)
  "knowledge_base_id": "string", // 知识库ID
  "created_at": "string",       // 处理时间 (ISO 8601)
  "completed_at": "string"      // 完成时间 (ISO 8601, 可选)
}
```

### StandardResponse - 标准响应

```json
{
  "success": true,            // 是否成功
  "message": "string",        // 响应消息
  "data": {}                 // 响应数据 (可选)
}
```

### ErrorResponse - 错误响应

```json
{
  "success": false,           // 固定为 false
  "message": "string",        // 错误消息
  "error_code": "string",     // 错误代码 (可选)
  "details": {}              // 错误详情 (可选)
}
```

---

## 错误代码

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 501 | 功能未实现 |

---

## 使用示例

### Python 示例

```python
import httpx
import asyncio

async def upload_and_process_document():
    """上传文件并处理到知识库的完整示例"""
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": "Bearer [REDACTED]"}
        
        # 1. 上传文件
        with open("document.pdf", "rb") as f:
            upload_response = await client.post(
                "http://localhost:8088/files",
                headers=headers,
                files={"file": f}
            )
        
        if upload_response.status_code == 200:
            file_info = upload_response.json()["file"]
            print(f"文件上传成功: {file_info['file_id']}")
            
            # 2. 处理到知识库
            process_response = await client.post(
                "http://localhost:8088/knowledge-bases/my_kb/documents",
                headers=headers,
                json={
                    "file_id": file_info["file_id"],
                    "mode": "simple"
                }
            )
            
            if process_response.status_code == 200:
                document = process_response.json()["document"]
                print(f"文档处理启动: {document['document_id']}")
            else:
                print(f"处理失败: {process_response.text}")
        else:
            print(f"上传失败: {upload_response.text}")

# 运行示例
# asyncio.run(upload_and_process_document())
```

### JavaScript 示例

```javascript
const uploadAndProcessDocument = async () => {
  const headers = {
    'Authorization': 'Bearer [REDACTED]'
  };

  try {
    // 1. 上传文件
    const formData = new FormData();
    const fileInput = document.getElementById('file-input');
    formData.append('file', fileInput.files[0]);

    const uploadResponse = await fetch('http://localhost:8088/files', {
      method: 'POST',
      headers: headers,
      body: formData
    });

    if (uploadResponse.ok) {
      const uploadResult = await uploadResponse.json();
      console.log('文件上传成功:', uploadResult.file.file_id);

      // 2. 处理到知识库
      const processResponse = await fetch(
        'http://localhost:8088/knowledge-bases/my_kb/documents',
        {
          method: 'POST',
          headers: {
            ...headers,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            file_id: uploadResult.file.file_id,
            mode: 'simple'
          })
        }
      );

      if (processResponse.ok) {
        const processResult = await processResponse.json();
        console.log('文档处理启动:', processResult.document.document_id);
      }
    }
  } catch (error) {
    console.error('操作失败:', error);
  }
};
```

---

## 开发状态

### ✅ 已实现功能

- 健康检查接口
- 文件类型查询  
- 文件上传、获取信息、删除
- Bearer Token 认证
- 用户权限验证
- 文档处理接口框架

### 🚧 开发中功能

- **知识库管理**:
  - 创建知识库
  - 获取知识库列表
  - 获取知识库信息
  - 删除知识库
- **文档管理**:
  - 获取知识库文档列表 (支持筛选、排序)
  - 获取文档详情
  - 删除知识库文档
- **文档处理**:
  - 外部URL文件处理
  - 实际文档处理逻辑
  - 处理状态跟踪

### 🔄 计划功能

- 批量文件操作
- 文件版本管理
- 文档全文搜索
- 向量检索接口
- 文档状态监控

---

## 更多信息

- **API交互式文档**: http://localhost:8088/docs
- **ReDoc文档**: http://localhost:8088/redoc
- **快速开始指南**: [QUICK_START.md](QUICK_START.md)
- **开发指南**: [DEVELOPMENT.md](DEVELOPMENT.md)
- **贡献指南**: [CONTRIBUTING.md](CONTRIBUTING.md)