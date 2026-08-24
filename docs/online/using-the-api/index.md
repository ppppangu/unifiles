# 使用 API

本节提供 Unifiles API 的详细使用指南，帮助你快速掌握各项功能。

## 导航指南

根据你的使用场景，选择合适的起点：

### 按任务选择

| 我想要... | 参考文档 |
|-----------|----------|
| 了解如何认证 | [认证方式](./authentication.md) |
| 上传和管理文件 | [文件和上传](./files-and-uploads.md) |
| 提取文档内容 | [内容提取](./content-extraction.md) |
| 创建知识库和搜索 | [知识库](./knowledge-bases.md) |
| 配置异步通知 | [Webhooks](./webhooks.md) |
| 了解配额限制 | [速率限制](./rate-limits.md) |
| 处理错误情况 | [错误处理](./error-handling.md) |

### 按层级选择

```
Layer 1: 文件管理
├── 认证方式 ─────────► authentication.md
└── 文件操作 ─────────► files-and-uploads.md

Layer 2: 内容提取
└── OCR 和提取 ───────► content-extraction.md

Layer 3: 知识库
└── 分块和检索 ───────► knowledge-bases.md

通用功能
├── 异步通知 ─────────► webhooks.md
├── 速率限制 ─────────► rate-limits.md
└── 错误处理 ─────────► error-handling.md
```

---

## 快速参考

### 安装 SDK

=== "pip"

    ```bash
    pip install unifiles-client
    ```

=== "uv"

    ```bash
    uv add unifiles-client
    ```

=== "poetry"

    ```bash
    poetry add unifiles-client
    ```

### 初始化客户端

```python
from unifiles import UnifilesClient

# 使用 API Key 初始化
client = UnifilesClient(api_key="sk_...")

# 自部署场景指定 base_url
client = UnifilesClient(
    api_key="sk_...",
    base_url="http://localhost:8088"
)
```

### 核心操作速查

```python
# Layer 1: 文件管理
file = client.files.upload("document.pdf")           # 上传
files = client.files.list(limit=50)                  # 列表
file = client.files.get(file_id)                     # 获取
client.files.delete(file_id)                         # 删除

# Layer 2: 内容提取
extraction = client.extractions.create(file_id)      # 创建
extraction.wait()                                     # 等待
extraction = client.extractions.get(extraction_id)   # 获取

# Layer 3: 知识库
kb = client.knowledge_bases.create(name="my-kb")     # 创建
doc = client.knowledge_bases.documents.create(kb_id, file_id)  # 添加文档
results = client.knowledge_bases.search(kb_id, query="...")    # 搜索
```

---

## API 端点概览

### REST API Base URL

| 环境 | Base URL |
|------|----------|
| SaaS 生产环境 | `https://api.unifiles.dev/v1` |
| 自部署 | `http://your-server:8088/v1` |

### 端点列表

| 资源 | 端点 | 说明 |
|------|------|------|
| **文件** | `POST /v1/files` | 上传文件 |
| | `GET /v1/files` | 列出文件 |
| | `GET /v1/files/{id}` | 获取文件 |
| | `DELETE /v1/files/{id}` | 删除文件 |
| **提取** | `POST /v1/extractions` | 创建提取任务 |
| | `GET /v1/extractions/{id}` | 获取提取结果 |
| **知识库** | `POST /v1/knowledge-bases` | 创建知识库 |
| | `GET /v1/knowledge-bases` | 列出知识库 |
| | `GET /v1/knowledge-bases/{id}` | 获取知识库 |
| | `DELETE /v1/knowledge-bases/{id}` | 删除知识库 |
| **文档** | `POST /v1/knowledge-bases/{id}/documents` | 添加文档 |
| | `GET /v1/knowledge-bases/{id}/documents` | 列出文档 |
| | `DELETE /v1/knowledge-bases/{id}/documents/{doc_id}` | 删除文档 |
| **搜索** | `POST /v1/knowledge-bases/{id}/search` | 语义搜索 |
| | `POST /v1/knowledge-bases/{id}/hybrid-search` | 混合搜索 |
| **Webhook** | `POST /v1/webhooks` | 创建 Webhook |
| | `GET /v1/webhooks` | 列出 Webhooks |
| | `DELETE /v1/webhooks/{id}` | 删除 Webhook |

---

## 下一步

<div class="grid cards" markdown>

-   :material-key: **认证方式**
    
    了解 API Key 的获取和使用
    
    [:octicons-arrow-right-24: authentication.md](./authentication.md)

-   :material-file-upload: **文件和上传**
    
    开始上传和管理文件
    
    [:octicons-arrow-right-24: files-and-uploads.md](./files-and-uploads.md)

</div>
