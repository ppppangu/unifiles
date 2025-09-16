# Unifiles API 设计规范

## API 概览

基于三层架构的RESTful API设计，提供完整的文档处理和知识库管理功能。

### API 版本和基础路径
- **基础URL**: `http://localhost:8088/api/v1`
- **API版本**: v1
- **认证方式**: Bearer Token
- **响应格式**: JSON

### 统一响应格式
```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "error": null,
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789"
}
```

## 第一层: 文件管理API

### 1.1 文件上传
```http
POST /api/v1/files
Content-Type: multipart/form-data
Authorization: Bearer [REDACTED]

# 请求体
{
  "file": <binary_file_data>,
  "filename": "document.pdf",
  "category": "document",
  "tags": ["important", "project-a"],
  "metadata": {
    "source": "web_upload",
    "description": "项目文档"
  }
}

# 响应
{
  "success": true,
  "message": "文件上传成功",
  "data": {
    "file_id": "file_123456789",
    "filename": "document.pdf",
    "original_filename": "document.pdf",
    "file_size": 1024000,
    "file_size_readable": "1.0 MB",
    "mime_type": "application/pdf",
    "file_hash": "sha256:abc123...",
    "status": "uploaded",
    "storage_path": "files/2024/01/01/file_123456789.pdf",
    "created_at": "2024-01-01T12:00:00Z",
    "processing_eligible": true
  }
}
```

### 1.2 文件信息查询
```http
GET /api/v1/files/{file_id}
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "data": {
    "file_id": "file_123456789",
    "filename": "document.pdf",
    "status": "processed",
    "processing_status": {
      "stage": "completed",
      "progress": 100,
      "message": "处理完成"
    },
    "metadata": {
      "pages": 10,
      "text_length": 5000,
      "images_count": 3
    },
    "created_at": "2024-01-01T12:00:00Z",
    "processed_at": "2024-01-01T12:05:00Z"
  }
}
```

### 1.3 文件列表
```http
GET /api/v1/files?page=1&size=20&status=processed&category=document
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "data": {
    "files": [
      {
        "file_id": "file_123456789",
        "filename": "document.pdf",
        "status": "processed",
        "file_size": 1024000,
        "created_at": "2024-01-01T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

### 1.4 文件下载
```http
GET /api/v1/files/{file_id}/download
Authorization: Bearer [REDACTED]

# 响应: 文件二进制流
Content-Type: application/pdf
Content-Disposition: attachment; filename="document.pdf"
```

### 1.5 文件删除
```http
DELETE /api/v1/files/{file_id}
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "message": "文件删除成功"
}
```

## 第二层: 文件处理API

### 2.1 启动文件处理
```http
POST /api/v1/extract
Authorization: Bearer [REDACTED]
Content-Type: application/json

# 请求体
{
  "file_id": "file_123456789",
  "processing_config": {
    "ocr_provider": "mineru",
    "extract_images": true,
    "extract_tables": true,
    "language": "zh-cn",
    "quality": "high"
  },
  "callback_url": "https://your-app.com/webhooks/processing"
}

# 响应
{
  "success": true,
  "message": "处理任务已启动",
  "data": {
    "job_id": "job_987654321",
    "file_id": "file_123456789",
    "status": "pending",
    "estimated_duration": "2-5分钟",
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

### 2.2 查询处理状态
```http
GET /api/v1/extract/jobs/{job_id}
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "data": {
    "job_id": "job_987654321",
    "file_id": "file_123456789",
    "status": "processing",
    "progress": 65,
    "current_stage": "ocr_extraction",
    "stages": [
      {
        "name": "validation",
        "status": "completed",
        "duration": "0.5s"
      },
      {
        "name": "ocr_extraction",
        "status": "processing",
        "progress": 65
      },
      {
        "name": "markdown_generation",
        "status": "pending"
      }
    ],
    "estimated_remaining": "1分钟",
    "created_at": "2024-01-01T12:00:00Z",
    "started_at": "2024-01-01T12:00:30Z"
  }
}
```

### 2.3 获取处理结果
```http
GET /api/v1/extract/jobs/{job_id}/result
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "data": {
    "job_id": "job_987654321",
    "file_id": "file_123456789",
    "extracted_document_id": "doc_456789123",
    "status": "completed",
    "result": {
      "markdown_content": "# 文档标题\n\n这是提取的内容...",
      "metadata": {
        "total_pages": 10,
        "total_chars": 5000,
        "total_words": 800,
        "images_extracted": 3,
        "tables_extracted": 2
      },
      "assets": [
        {
          "asset_id": "asset_111",
          "type": "image",
          "filename": "image_1.png",
          "description": "图表显示销售数据"
        }
      ]
    },
    "performance": {
      "total_duration": "3.2s",
      "ocr_duration": "2.1s",
      "parsing_duration": "1.1s"
    },
    "completed_at": "2024-01-01T12:03:20Z"
  }
}
```

### 2.4 取消处理任务
```http
DELETE /api/v1/extract/jobs/{job_id}
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "message": "处理任务已取消"
}
```

## 第三层: 知识库管理API

### 3.1 创建知识库
```http
POST /api/v1/knowledge-bases
Authorization: Bearer [REDACTED]
Content-Type: application/json

# 请求体
{
  "name": "project_docs",
  "display_name": "项目文档库",
  "description": "存储所有项目相关文档",
  "config": {
    "chunking_strategy": {
      "type": "markdown_hierarchical",
      "max_chunk_size": 1000,
      "overlap_size": 100
    },
    "embedding_model": "text-embedding-3-small",
    "search_config": {
      "enable_hybrid_search": true,
      "similarity_threshold": 0.7
    }
  },
  "tags": ["project", "documentation"]
}

# 响应
{
  "success": true,
  "message": "知识库创建成功",
  "data": {
    "kb_id": "kb_789123456",
    "name": "project_docs",
    "display_name": "项目文档库",
    "status": "active",
    "document_count": 0,
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

### 3.2 索引文档到知识库
```http
POST /api/v1/knowledge-bases/{kb_id}/documents
Authorization: Bearer [REDACTED]
Content-Type: application/json

# 请求体
{
  "file_id": "file_123456789",
  "title": "项目需求文档",
  "description": "详细的项目需求说明",
  "custom_config": {
    "chunking_strategy": {
      "type": "semantic",
      "max_chunk_size": 800
    }
  },
  "tags": ["requirements", "v1.0"],
  "auto_process": true
}

# 响应
{
  "success": true,
  "message": "文档索引已启动",
  "data": {
    "document_id": "doc_456789123",
    "kb_id": "kb_789123456",
    "file_id": "file_123456789",
    "title": "项目需求文档",
    "indexing_job_id": "idx_job_111222",
    "status": "indexing",
    "estimated_duration": "30秒",
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

### 3.3 知识库搜索
```http
POST /api/v1/knowledge-bases/{kb_id}/search
Authorization: Bearer [REDACTED]
Content-Type: application/json

# 请求体
{
  "query": "项目需求中的用户认证功能",
  "search_type": "hybrid",
  "filters": {
    "tags": ["requirements"],
    "document_types": ["pdf", "docx"]
  },
  "limit": 10,
  "include_metadata": true,
  "highlight": true
}

# 响应
{
  "success": true,
  "data": {
    "query": "项目需求中的用户认证功能",
    "results": [
      {
        "chunk_id": "chunk_111",
        "document_id": "doc_456789123",
        "document_title": "项目需求文档",
        "content": "用户认证功能需要支持多种登录方式...",
        "highlighted_content": "用户<mark>认证</mark>功能需要支持多种登录方式...",
        "similarity_score": 0.92,
        "text_score": 0.85,
        "combined_score": 0.89,
        "metadata": {
          "page": 5,
          "section": "功能需求",
          "chunk_index": 12
        }
      }
    ],
    "total_results": 15,
    "search_time_ms": 45,
    "filters_applied": {
      "tags": ["requirements"]
    }
  }
}
```

### 3.4 对话式查询
```http
POST /api/v1/knowledge-bases/{kb_id}/chat
Authorization: Bearer [REDACTED]
Content-Type: application/json

# 请求体
{
  "message": "用户认证功能有哪些具体要求？",
  "conversation_id": "conv_123456",
  "context_limit": 5,
  "include_sources": true
}

# 响应
{
  "success": true,
  "data": {
    "conversation_id": "conv_123456",
    "message": "用户认证功能有哪些具体要求？",
    "response": "根据项目需求文档，用户认证功能包括以下要求：\n1. 支持邮箱和手机号登录\n2. 支持第三方登录（微信、QQ）\n3. 密码强度验证\n4. 登录失败锁定机制",
    "sources": [
      {
        "document_title": "项目需求文档",
        "chunk_content": "用户认证功能需要支持...",
        "page": 5,
        "confidence": 0.92
      }
    ],
    "response_time_ms": 1200,
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

### 3.5 知识库统计
```http
GET /api/v1/knowledge-bases/{kb_id}/statistics
Authorization: Bearer [REDACTED]

# 响应
{
  "success": true,
  "data": {
    "kb_id": "kb_789123456",
    "name": "project_docs",
    "statistics": {
      "total_documents": 25,
      "total_chunks": 1250,
      "total_characters": 125000,
      "total_words": 25000,
      "total_searches": 150,
      "avg_search_time_ms": 45,
      "most_searched_topics": [
        "用户认证",
        "数据库设计",
        "API接口"
      ]
    },
    "recent_activity": {
      "last_document_added": "2024-01-01T10:00:00Z",
      "last_search": "2024-01-01T11:30:00Z",
      "documents_added_today": 3,
      "searches_today": 12
    }
  }
}
```

## 错误处理

### 错误响应格式
```json
{
  "success": false,
  "message": "操作失败",
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "指定的文件不存在",
    "details": {
      "file_id": "file_123456789"
    }
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789"
}
```

### 常见错误码
- `UNAUTHORIZED` (401): 认证失败
- `FORBIDDEN` (403): 权限不足
- `FILE_NOT_FOUND` (404): 文件不存在
- `INVALID_FILE_FORMAT` (400): 不支持的文件格式
- `FILE_TOO_LARGE` (413): 文件过大
- `PROCESSING_FAILED` (500): 处理失败
- `RATE_LIMIT_EXCEEDED` (429): 请求频率超限

## 认证和权限

### Bearer Token认证
```http
Authorization: Bearer [REDACTED]
```

### 权限范围
- `files:read` - 读取文件
- `files:write` - 上传和修改文件
- `files:delete` - 删除文件
- `extract:create` - 创建处理任务
- `kb:read` - 读取知识库
- `kb:write` - 修改知识库
- `kb:admin` - 管理知识库

---

*此API设计规范提供了完整的三层架构API接口定义，支持文件管理、处理和知识库的全生命周期操作。*
