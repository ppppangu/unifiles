# RAG PDF处理服务 API文档

## 概述

本文档描述了RAG PDF处理服务的API接口。该服务提供PDF文件处理、文本提取、分块、嵌入和向量数据库存储功能，支持知识库构建和RAG（检索增强生成）应用。

服务包含两个主要应用：
1. FastAPI应用（`src/main.py`）- 提供PDF处理和任务管理功能
2. Starlette应用（`main.py`）- 提供文件上传和处理模式选择功能

## 基本信息

- **基础URL**: `http://127.0.0.1:8080` (FastAPI应用) 或 `http://0.0.0.0:8000` (Starlette应用)
- **API文档**: `/docs` (仅FastAPI应用提供Swagger UI)
- **内容类型**: 
  - 请求: `application/json`, `multipart/form-data`
  - 响应: `application/json`

## 健康检查

### 1. 检查服务健康状态

**FastAPI应用**

```
GET /health
```

**Starlette应用**

```
GET /health
```

**响应**:

```json
{
  "status": "healthy"
}
```

或

```json
{
  "status": "ok"
}
```

## FastAPI应用接口

### 1. 处理PDF文件

```
POST /process-pdf/
```

**描述**: 处理PDF文件，提取文本，分块，生成嵌入向量，并存储到数据库中。处理过程在后台异步执行。

**请求格式**: `multipart/form-data`

**参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| knowledge_base_id | string | 是 | 知识库ID |
| document_id | string | 是 | 文档ID |
| pdf_file_url | string | 否* | PDF文件的URL地址 |
| pdf_file | file | 否* | 上传的PDF文件 |
| job_id | string | 否 | 任务ID，如不提供则自动生成 |
| mode | string | 否 | 处理模式，目前仅支持"simple"（默认） |

\* `pdf_file_url` 和 `pdf_file` 至少需要提供一个

**响应**:

```json
{
  "status": "accepted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**错误响应**:

```json
{
  "detail": "pdf_file_url 与 pdf_file 必须至少提供一个"
}
```

或

```json
{
  "detail": "目前仅支持 simple 模式"
}
```

或

```json
{
  "detail": "下载 PDF 失败: ..."
}
```

### 2. 查询任务状态

```
GET /jobs/{job_id}
```

**描述**: 查询指定任务ID的处理状态。

**参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| job_id | string | 是 | 任务ID |

**响应**:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": null
}
```

或

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": null
}
```

或

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "message": "已写入 42 chunks"
}
```

或

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "message": "错误详情..."
}
```

**错误响应**:

```json
{
  "detail": "job_id 未找到"
}
```

## Starlette应用接口

### 1. 主页

```
GET /
```

**响应**:

```json
{
  "message": "Hello, World!"
}
```

### 2. 获取支持的处理模式

```
GET /get_mode
```

**响应**:

```json
{
  "mode": ["vector", "graph"]
}
```

### 3. 上传文件

```
POST /upload
```

**描述**: 上传文件并进行处理，支持向量化和图形化两种模式。

**请求格式**: `multipart/form-data`

**参数**:

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| knowledge_base_id | string | 是 | 知识库ID |
| document_id | string | 是 | 文档ID |
| user_id | string | 是 | 用户ID |
| job_id | string | 否 | 任务ID |
| pdf_file_url | string | 是 | PDF文件的URL地址 |
| mode | array | 否 | 处理模式，支持"vector"和"graph"，默认为"vector" |
| parse_method | string | 否 | 解析方法，默认为"simple" |

**响应**:

```json
{
  "status": "ok"
}
```

**错误响应**:

```json
{
  "status": "error",
  "message": "knowledge_base_id / document_id / pdf_file_url are required"
}
```

或

```json
{
  "status": "error",
  "message": "user_id is required"
}
```

或

```json
{
  "status": "error",
  "message": "there is no user_id for this knowledge_base_id, please user_id and knowledge_base_id are whether match"
}
```

## 任务状态说明

任务状态包括以下几种：

- **queued**: 任务已加入队列，等待处理
- **processing**: 任务正在处理中
- **success**: 任务处理成功
- **failed**: 任务处理失败

## 处理流程说明

### Simple模式处理流程

1. 提取文本（包含OCR描述）
2. 文本分块
3. 生成嵌入向量
4. 写入数据库

## 注意事项

1. FastAPI应用和Starlette应用提供的功能有所重叠，但实现方式不同
2. 目前FastAPI应用仅支持"simple"处理模式
3. Starlette应用支持"vector"和"graph"两种处理模式
4. 任务状态仅在当前服务实例的内存中保存，服务重启后将丢失
