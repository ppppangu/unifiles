# UnifilesClient

主客户端类，所有 API 操作的入口。

## 构造函数

```python
UnifilesClient(
    api_key: str = None,
    base_url: str = "https://api.unifiles.dev",
    timeout: int = 30,
    max_retries: int = 3
)
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `api_key` | str | None | API Key，未提供时从环境变量读取 |
| `base_url` | str | `https://api.unifiles.dev` | API 服务地址 |
| `timeout` | int | 30 | 请求超时（秒） |
| `max_retries` | int | 3 | 失败重试次数 |

`base_url` 填服务地址即可，SDK 会自动补上 `/v1`。`client.raw` 是 generated
协议入口，适合低层调用；常规业务代码应使用上面的 public resource facade。

### 示例

```python
from unifiles import UnifilesClient

# 基本用法
client = UnifilesClient(api_key="<api-key>")

# 从环境变量读取
# export UNIFILES_API_KEY=<api-key>
client = UnifilesClient()

# 自定义配置
client = UnifilesClient(
    api_key="<api-key>",
    base_url="https://your-server.com",
    timeout=60,
    max_retries=5
)
```

## 命名空间

### client.files

文件管理命名空间。

```python
client.files.upload(path)      # 上传文件
client.files.list()            # 列出文件
client.files.get(file_id)      # 获取文件
client.files.delete(file_id)   # 删除文件
client.files.download(file_id) # 下载文件
```

### client.extractions

内容提取命名空间。

```python
client.extractions.create(file_id)  # 创建提取任务
client.extractions.get(extraction_id)  # 获取提取结果
client.extractions.list(file_id)    # 获取文件的提取记录
```

### client.knowledge_bases

知识库命名空间。

```python
client.knowledge_bases.create(name)     # 创建知识库
client.knowledge_bases.list()           # 列出知识库
client.knowledge_bases.get(kb_id)       # 获取知识库
client.knowledge_bases.update(kb_id)    # 更新知识库
client.knowledge_bases.delete(kb_id)    # 删除知识库
client.knowledge_bases.search(kb_id, query)  # 搜索
client.knowledge_bases.hybrid_search(kb_id, query)  # 混合搜索
```

### client.knowledge_bases.documents

知识库文档命名空间。

```python
client.knowledge_bases.documents.create(kb_id, file_id)  # 添加文档
client.knowledge_bases.documents.list(kb_id)             # 列出文档
client.knowledge_bases.documents.get(kb_id, doc_id)      # 获取文档
client.knowledge_bases.documents.delete(kb_id, doc_id)   # 删除文档
```

### client.webhooks

Webhook 命名空间。

```python
client.webhooks.create(url, events)  # 创建 Webhook
client.webhooks.list()               # 列出 Webhooks
client.webhooks.get(webhook_id)      # 获取 Webhook
client.webhooks.update(webhook_id)   # 更新 Webhook
client.webhooks.delete(webhook_id)   # 删除 Webhook
```

### client.api_keys

API Key 命名空间。

```python
client.api_keys.create(name)   # 创建 API Key
client.api_keys.list()         # 列出 API Keys
client.api_keys.revoke(key_id) # 撤销 API Key
```

### client.usage

使用统计命名空间。

```python
client.usage.stats()   # 获取使用统计
client.usage.limits()  # 获取配额限制
```

### client.system

系统状态命名空间。

```python
client.system.health()     # 版本化健康检查
client.system.liveness()   # 存活检查
client.system.details()    # 详细健康状态
```

## 上下文管理器

```python
with UnifilesClient(api_key="<api-key>") as client:
    file = client.files.upload("doc.pdf")
    # 自动清理资源
```

## 线程安全

`UnifilesClient` 是线程安全的，可以在多线程环境中共享：

```python
from concurrent.futures import ThreadPoolExecutor

client = UnifilesClient(api_key="<api-key>")

def upload_file(path):
    return client.files.upload(path)

with ThreadPoolExecutor(max_workers=5) as executor:
    files = list(executor.map(upload_file, file_paths))
```
