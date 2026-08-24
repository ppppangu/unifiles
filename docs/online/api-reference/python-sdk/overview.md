# Python SDK 概述

Unifiles Python SDK 提供类型安全、符合 Python 习惯的 API 接入方式。分发包名为
`unifiles-client`，导入模块仍为 `unifiles`。

## 安装

```bash
pip install unifiles-client
```

支持同步 `UnifilesClient` 和异步 `AsyncUnifilesClient`：

```python
from unifiles import AsyncUnifilesClient

async with AsyncUnifilesClient(api_key="sk_...") as client:
    file = await client.files.upload("document.pdf")
    extraction = await client.extractions.create(file.id)
    await extraction.wait()
```

## 快速开始

```python
from unifiles import UnifilesClient

# 初始化客户端
client = UnifilesClient(api_key="sk_...")

# 上传文件
file = client.files.upload("document.pdf")

# 提取内容
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 创建知识库并搜索
kb = client.knowledge_bases.create(name="my-kb")
client.knowledge_bases.documents.create(kb_id=kb.id, file_id=file.id).wait()

results = client.knowledge_bases.search(kb_id=kb.id, query="查询内容")
```

## 客户端配置

```python
client = UnifilesClient(
    api_key="sk_...",              # API Key（必需）
    base_url="https://...",        # 自定义服务地址
    timeout=30,                    # 请求超时（秒）
    max_retries=3                  # 最大重试次数
)
```

### 环境变量

```bash
export UNIFILES_API_KEY=sk_...
export UNIFILES_BASE_URL=https://...
```

```python
# 自动读取环境变量
client = UnifilesClient()
```

## 命名空间结构

```
client
├── files           # 文件管理
├── extractions     # 内容提取
├── knowledge_bases # 知识库
│   └── documents   # 文档管理
├── webhooks        # Webhook
├── api_keys        # API Key 管理
└── usage           # 使用统计
```

## 错误处理

```python
from unifiles.exceptions import (
    UnifilesError,
    AuthenticationError,
    NotFoundError,
    RateLimitError
)

try:
    file = client.files.get("invalid_id")
except NotFoundError:
    print("文件不存在")
except RateLimitError as e:
    print(f"请在 {e.retry_after} 秒后重试")
except UnifilesError as e:
    print(f"错误: {e.message}")
```

## 类型支持

SDK 提供完整的类型注解，支持 IDE 自动补全：

```python
from unifiles import UnifilesClient
from unifiles.types import File, Extraction, KnowledgeBase

client = UnifilesClient(api_key="sk_...")

file: File = client.files.upload("doc.pdf")
extraction: Extraction = client.extractions.create(file_id=file.id)
```

## 下一步

- [Client](client.md) - 客户端详细配置
- [Files](files.md) - 文件操作
- [Extractions](extractions.md) - 内容提取
- [Knowledge Bases](knowledge-bases.md) - 知识库操作
- [Types](types.md) - 数据类型定义
- [Exceptions](exceptions.md) - 异常类型
