# API Documentation

Unifiles 提供基于 RESTful 风格的 HTTP API，让您可以轻松地集成文件处理和知识库功能到您的应用中。

## API 概览

### 基础信息

- **Base URL**: `http://your-server:8088/api/v1`
- **认证方式**: Bearer Token (API Key)
- **数据格式**: JSON
- **字符编码**: UTF-8

### 核心资源

#### 1. Files（文件管理）
文件上传、下载、删除和元数据管理。

**主要端点**:
- `POST /files` - 上传文件
- `GET /files/{file_id}` - 获取文件信息
- `GET /files/{file_id}/download` - 下载文件
- `DELETE /files/{file_id}` - 删除文件

[查看详细文档](reference.md#files)

#### 2. Processors（内容提取）
触发和管理文档处理任务。

**主要端点**:
- `POST /processors/extract` - 启动内容提取
- `GET /processors/status/{task_id}` - 查询处理状态
- `GET /processors/result/{task_id}` - 获取提取结果

[查看详细文档](reference.md#processors)

#### 3. Knowledge Bases（知识库）
创建知识库、索引文档、搜索内容。

**主要端点**:
- `POST /knowledge-bases` - 创建知识库
- `GET /knowledge-bases` - 列出知识库
- `POST /knowledge-bases/{kb_id}/documents` - 添加文档
- `POST /knowledge-bases/{kb_id}/search` - 搜索知识库

[查看详细文档](reference.md#knowledge-bases)

## 快速开始

### 1. 获取 API Key

```bash
# 注册用户并获取 API Key
curl -X POST http://your-server:8088/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-username",
    "password": "your-password"
  }'
```

### 2. 上传文件

```bash
# 使用 API Key 上传文件
curl -X POST http://your-server:8088/api/v1/files \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@/path/to/document.pdf"
```

### 3. 提取内容

```bash
# 启动内容提取
curl -X POST http://your-server:8088/api/v1/processors/extract \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID_FROM_STEP_2"
  }'
```

### 4. 创建知识库并搜索

```bash
# 创建知识库
curl -X POST http://your-server:8088/api/v1/knowledge-bases \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Knowledge Base",
    "description": "My first knowledge base"
  }'

# 搜索知识库
curl -X POST http://your-server:8088/api/v1/knowledge-bases/KB_ID/search \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is this document about?",
    "top_k": 5
  }'
```

## 认证

所有 API 请求都需要在 HTTP Header 中包含 API Key：

```
Authorization: Bearer [REDACTED]
```

示例：

```python
import requests

headers = {
    "Authorization": "Bearer sk_live_your_api_key_here"
}

response = requests.get(
    "http://your-server:8088/api/v1/files",
    headers=headers
)
```

## 错误处理

### 标准响应格式

所有 API 响应都遵循统一的格式：

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "error": null
}
```

### 错误响应

```json
{
  "success": false,
  "data": null,
  "message": "Error message",
  "error": {
    "code": "ERROR_CODE",
    "details": { ... }
  }
}
```

### HTTP 状态码

- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 认证失败
- `403 Forbidden` - 权限不足
- `404 Not Found` - 资源不存在
- `429 Too Many Requests` - 请求过于频繁
- `500 Internal Server Error` - 服务器内部错误

## 速率限制

为了保护服务稳定性，API 实施以下速率限制：

- **文件上传**: 100 次/小时
- **内容提取**: 50 次/小时
- **知识库搜索**: 1000 次/小时

超过限制时，API 将返回 `429 Too Many Requests` 状态码。

## SDKs

### Python SDK

```python
from unifiles_client import UnifilesCLient

client = UnifilesClient(api_key="[REDACTED]")

# 上传文件
file = client.files.upload("document.pdf")

# 提取内容
task = client.processors.extract(file.id)

# 等待处理完成
result = task.wait()

# 创建知识库
kb = client.knowledge_bases.create("My KB")

# 添加文档
kb.add_document(file.id)

# 搜索
results = kb.search("your query")
```

[Python SDK 文档](https://github.com/ppppangu/unifiles-client-python)

## 进一步阅读

- [API 参考](reference.md) - 完整的 API 端点文档
- [设计规范](design-spec.md) - API 设计原则和规范
- [OpenAPI 规范](openapi.yaml) - 机器可读的 API 定义
- [认证授权](authentication.md) - 详细的认证机制说明
