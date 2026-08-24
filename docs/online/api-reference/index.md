# API 参考

Unifiles 提供 REST API、Python SDK、TypeScript SDK 和 Unix CLI 四种接入方式。

## 接入方式

| 方式 | 适用场景 | 文档 |
|-----|---------|------|
| REST API | 任何编程语言、HTTP 客户端 | [REST API 参考](rest-api/overview.md) |
| Python SDK | Python 应用程序 | [Python SDK 参考](python-sdk/overview.md) |
| TypeScript SDK | Node.js 服务 | [TypeScript SDK 参考](typescript-sdk/index.md) |
| CLI | 终端与自动化脚本 | [CLI 参考](cli.md) |

## 快速对比

### REST API

```bash
curl -X POST https://api.unifiles.dev/v1/files \
  -H "Authorization: Bearer sk_..." \
  -F "file=@document.pdf"
```

### Python SDK

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")
file = client.files.upload("document.pdf")
```

### TypeScript SDK

```typescript
import { UnifilesClient } from "@wyy/unifiles";

const client = new UnifilesClient({ apiKey: "sk_..." });
const file = await client.files.upload("document.pdf");
```

### CLI

```bash
unifiles files upload document.pdf
```

## API 基础信息

### Base URL

```
https://api.unifiles.dev/v1
```

自部署环境使用你自己的域名。

### 认证

所有请求需要在 Header 中包含 API Key：

```
Authorization: Bearer sk_your_api_key
```

### 请求格式

- 请求体使用 JSON 格式（文件上传除外）
- 字符编码 UTF-8
- Content-Type: `application/json`

### 响应格式

所有响应都是 JSON 格式：

```json
{
    "id": "file_abc123",
    "filename": "document.pdf",
    "size": 1048576,
    "created_at": "2024-01-15T10:30:00Z"
}
```

错误响应：

```json
{
    "error": {
        "code": "INVALID_REQUEST",
        "message": "请求参数无效",
        "request_id": "req_xyz789"
    }
}
```

## 端点概览

### Files（文件）

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/v1/files` | 上传文件 |
| GET | `/v1/files` | 列出文件 |
| GET | `/v1/files/{id}` | 获取文件详情 |
| DELETE | `/v1/files/{id}` | 删除文件 |
| GET | `/v1/files/{id}/download` | 下载文件 |

### Extractions（内容提取）

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/v1/extractions` | 创建提取任务 |
| GET | `/v1/extractions/{id}` | 获取提取状态/结果 |

### Knowledge Bases（知识库）

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/v1/knowledge-bases` | 创建知识库 |
| GET | `/v1/knowledge-bases` | 列出知识库 |
| GET | `/v1/knowledge-bases/{id}` | 获取知识库详情 |
| PATCH | `/v1/knowledge-bases/{id}` | 更新知识库 |
| DELETE | `/v1/knowledge-bases/{id}` | 删除知识库 |
| POST | `/v1/knowledge-bases/{id}/documents` | 添加文档 |
| POST | `/v1/knowledge-bases/{id}/search` | 语义搜索 |

### Webhooks

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/v1/webhooks` | 创建 Webhook |
| GET | `/v1/webhooks` | 列出 Webhooks |
| DELETE | `/v1/webhooks/{id}` | 删除 Webhook |

### API Keys

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | `/v1/api-keys` | 创建 API Key |
| GET | `/v1/api-keys` | 列出 API Keys |
| DELETE | `/v1/api-keys/{id}` | 撤销 API Key |

## SDK 命名空间

Python SDK 使用命名空间组织 API：

```python
client = UnifilesClient(api_key="sk_...")

# Files
client.files.upload()
client.files.list()
client.files.get()
client.files.delete()
client.files.download()

# Extractions
client.extractions.create()
client.extractions.get()

# Knowledge Bases
client.knowledge_bases.create()
client.knowledge_bases.list()
client.knowledge_bases.get()
client.knowledge_bases.update()
client.knowledge_bases.delete()
client.knowledge_bases.search()
client.knowledge_bases.hybrid_search()

# Knowledge Base Documents
client.knowledge_bases.documents.create()
client.knowledge_bases.documents.list()
client.knowledge_bases.documents.get()
client.knowledge_bases.documents.delete()

# Webhooks
client.webhooks.create()
client.webhooks.list()
client.webhooks.get()
client.webhooks.delete()

# API Keys
client.api_keys.create()
client.api_keys.list()
client.api_keys.delete()

# Usage
client.usage.get_stats()
client.usage.get_limits()
```

## 下一步

- [REST API 参考](rest-api/overview.md) - 完整的 REST API 文档
- [Python SDK 参考](python-sdk/overview.md) - Python SDK 详细文档
- [错误码参考](rest-api/errors.md) - 错误码列表
