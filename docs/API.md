# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:8087`
- **Content-Type**: `application/json` 或 `multipart/form-data`

## 通用响应格式

```json
{
  "status": "ok|error",
  "message": "描述信息",
  "data": {}
}
```

## 接口列表

### 1. 健康检查

#### 1.1 服务健康检查
- **URL**: `/health`
- **Method**: `GET`
- **描述**: 检查服务是否正常运行

**响应示例**:
```json
{
  "status": "ok",
  "message": "Service is healthy"
}
```

#### 1.2 获取支持的文件类型
- **URL**: `/get_supported_file_types`
- **Method**: `GET`
- **描述**: 获取服务支持的文件类型列表

**响应示例**:
```json
{
  "status": "ok",
  "message": "Supported file types",
  "data": {
    "supported_file_types": [".pdf", ".docx", ".txt", ".md"]
  }
}
```

### 2. 文件管理

#### 2.1 文件上传
- **URL**: `/upload_minio`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **描述**: 上传文件到MinIO存储

**请求参数**:
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| upload_file | File | ✓ | - | 要上传的文件 |
| user_id | string | ✗ | "default" | 用户ID |

**响应示例**:
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "data": {
    "file_url": "http://minio:9000/bucket/path/file.pdf",
    "file_id": "uuid-string",
    "file_name": "document.pdf"
  }
}
```

#### 2.2 文件处理
- **URL**: `/process`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **描述**: 处理上传的文件（OCR、向量化等）

**请求参数**:
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| user_id | string | ✓ | - | 用户ID |
| file_url | string | ✓ | - | 文件URL |
| knowledge_base_id | string | ✗ | "df_{user_id}" | 知识库ID |
| mode | string | ✗ | "simple" | 处理模式 |

**处理模式**:
- `simple`: 基础向量化处理
- `normal`: 基础文件处理

**响应示例**:
```json
{
  "status": "ok",
  "message": "File processed successfully",
  "data": {
    "user_id": "user123",
    "knowledge_base_id": "df_user123",
    "mode": "simple",
    "file_url": "http://minio:9000/bucket/original.pdf",
    "file_uuid": "uuid-string",
    "markdown_public_url": "http://minio:9000/bucket/processed.md",
    "pdf_file_public_url": "http://minio:9000/bucket/converted.pdf"
  }
}
```

#### 2.3 文件删除
- **URL**: `/delete_file`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **描述**: 从系统中删除文件

**请求参数**:
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| user_id | string | ✓ | - | 用户ID |
| file_id | string | ✓ | - | 文件ID |
| knowledge_base_id | string | ✗ | "df_{user_id}" | 知识库ID |

**响应示例**:
```json
{
  "status": "ok",
  "message": "File deleted successfully"
}
```

### 3. 知识图谱

#### 3.1 图谱管理
- **URL**: `/graph/knowledge_base`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **描述**: 生成或获取知识图谱

**请求参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| user_id | string | ✓ | 用户ID |
| knowledge_base_id | string | ✓ | 知识库ID |
| mode | string | ✓ | 操作模式：produce(生成) / get(获取) |
| level | string | ✓ | 图谱级别：document(文档级) / subject(主题级) |

**响应示例**:
```json
{
  "status": "ok",
  "message": "Document graph produced successfully",
  "data": {
    "graph_id": "graph-uuid",
    "nodes": [],
    "edges": []
  }
}
```

## 错误码

| HTTP状态码 | 错误类型 | 描述 |
|------------|----------|------|
| 400 | Bad Request | 请求参数错误 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |

## 使用示例

### cURL示例

```bash
# 健康检查
curl -X GET http://localhost:8087/health

# 文件上传
curl -X POST http://localhost:8087/upload_minio \
  -F "upload_file=@/path/to/file.pdf" \
  -F "user_id=user123"

# 文件处理
curl -X POST http://localhost:8087/process \
  -F "user_id=user123" \
  -F "file_url=http://minio:9000/bucket/file.pdf" \
  -F "mode=simple"
```

### Python示例

```python
import requests

# 文件上传
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8087/upload_minio',
        files={'upload_file': f},
        data={'user_id': 'user123'}
    )
    print(response.json())

# 文件处理
response = requests.post(
    'http://localhost:8087/process',
    data={
        'user_id': 'user123',
        'file_url': 'http://minio:9000/bucket/file.pdf',
        'mode': 'simple'
    }
)
print(response.json())
```