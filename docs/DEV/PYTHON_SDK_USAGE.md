# Python SDK 使用指南（unifiles-client）

本文档介绍如何在 Python 中使用 Unifiles 客户端 SDK，涵盖安装、鉴权、文件上传与内容提取、知识库索引与检索，以及错误处理与最佳实践。示例基于客户端实现：`unifiles/client/client.py`。

- 包名称: `unifiles-client`
- 导入包名: `unifiles_client`
- 默认服务地址: `http://localhost:8088`（建议明确传入）

---

## 安装与环境

- 本地源码安装（开发模式）:
  - `uv sync --dev` 或 `pip install -e .[dev]`
- 生产安装（若已发布到仓库）:
  - `pip install unifiles-client`
- 准备 API 服务:
  - 启动后端：`uv run uvicorn unifiles.app.main:app --host 0.0.0.0 --port 8088 --reload`

建议使用环境变量管理配置（不要硬编码密钥）：

```bash
export UNIFILES_API_KEY="sk_..."
export UNIFILES_API_BASE_URL="http://127.0.0.1:8088"
```

---

## 快速开始

```python
import os
from unifiles_client import Unifile

api_key = os.environ["UNIFILES_API_KEY"]
base_url = os.getenv("UNIFILES_API_BASE_URL", "http://127.0.0.1:8088")

client = Unifile(api_key=api_key, base_url=base_url)

# 1) 上传文件（第一层：文件存储）
doc = client.upload_file("/path/to/file.pdf", is_public=False)

# 2) 触发内容提取（第二层：OCR/文本解析）
extract_resp = doc.extract_content(mode="simple")  # simple/mistral/mineru/selfhosted

# 3) 创建知识库并将文档索引进去（第三层：分块+向量化）
kb = client.create_knowledge_base("My Knowledge Base")
index_resp = doc.index_to_knowledge_base(kb.kb_id, chunk_strategy="semantic")

# 4) 检索
results = kb.search("电气自动化设备安装", top_k=5)
for r in results:
    print(r.similarity_score, r.text_content[:80])
```

---

## 客户端初始化

```python
from unifiles_client import Unifile

client = Unifile(
    api_key="sk_xxx",                      # 必填：访问密钥（Bearer Token）
    base_url="http://127.0.0.1:8088",      # 建议显式传入，与后端端口一致
)
```

- 身份认证通过请求头 `Authorization: Bearer <token>` 自动完成。
- 若服务部署在不同主机/端口，请调整 `base_url`。

---

## 文件存储层（第一层）

- 上传文件：`upload_file(file_path, is_public=False) -> Document`
- 列出文件：`list_files(limit=50, offset=0) -> list[Document]`
- 获取文档对象：`get_document(file_id) -> Document`
- 删除文件：`delete_file(file_id) -> bool`

注意：客户端内置文件校验
- 支持扩展名：`.pdf .doc .docx .txt .md .jpg .jpeg .png .tiff`
- 最大大小：100 MB

示例：

```python
from unifiles_client import Unifile

client = Unifile(api_key=api_key, base_url=base_url)

# 上传
doc = client.upload_file("docs/sample.pdf", is_public=False)
print(doc.file_id, doc.filename, doc.file_size)

# 列表
for d in client.list_files(limit=10):
    print(d.file_id, d.filename)

# 删除
ok = client.delete_file(doc.file_id)
```

---

## 内容提取层（第二层）

- 触发提取：`Document.extract_content(mode="...") -> dict`
- 获取内容：`Document.get_content(content_type=None|ContentType.TEXT|ContentType.IMAGE)`
- 等待完成：`Document.wait_for_extraction(timeout=300, poll_interval=5) -> bool`

提取模式（与服务端一致）：
- `simple`: 基础文本提取
- `mistral`: 多模态 OCR（例如 Mistral）
- `mineru`: 多模态提取（Mineru）
- `selfhosted`: 自托管多模态模型

示例：

```python
from unifiles_client import ContentType

# 触发提取
doc.extract_content(mode="mistral")

# 可选：等待（长任务时使用）
# doc.wait_for_extraction(timeout=600, poll_interval=5)

# 获取全部提取结果（可能包含文本+Markdown/OCR）
content = doc.get_content()
print(content.get("extraction_id"))

# 仅取文本内容
text_part = doc.get_content(ContentType.TEXT)
print(text_part["content"][:200])

# 仅取图片/OCR转Markdown
image_part = doc.get_content(ContentType.IMAGE)
print(image_part["content"][:200])
```

返回结构（示例，详见 API 文档 `docs/DEV/API_ENDPOINTS.md`）:

```json
{
  "success": true,
  "extracted_content": {
    "file_id": "file_xxx",
    "extraction_id": "extract_abc123",
    "extracted_text": "...",
    "markdown_content": "...",
    "extraction_strategy": "OCR-mistral",
    "status": "completed"
  }
}
```

---

## 知识库索引与检索（第三层）

- 创建知识库：`create_knowledge_base(name, description="") -> KnowledgeBase`
- 获取知识库对象：`get_knowledge_base(kb_id) -> KnowledgeBase`
- 列出知识库：`list_knowledge_bases(limit=50, offset=0) -> list[KnowledgeBase]`
- 将文档索引进知识库：`Document.index_to_knowledge_base(kb_id, chunk_strategy="semantic")`
- 在知识库中检索：`KnowledgeBase.search(query, top_k=10) -> list[SearchResult]`

分块策略：
- `fixed_size` 固定大小
- `semantic` 语义分块（默认）
- `recursive` 递归分块

示例：

```python
# 创建/获取知识库
kb = client.create_knowledge_base("Contracts")

# 将已提取内容的文档索引进知识库
doc.index_to_knowledge_base(kb.kb_id, chunk_strategy="semantic")

# 向量检索
results = kb.search("保密条款 有效期", top_k=5)
for item in results:
    print(f"score={item.similarity_score:.3f}", item.text_content[:80])
```

还有一键流程：

```python
processed_doc = client.quick_process(
    file_path="docs/sample.pdf",
    knowledge_base_name="Contracts",
    extract_mode="simple",
)
```

---

## 错误处理与常见问题

统一异常类型：`UnifilesError`。

```python
from unifiles_client import UnifilesError

try:
    doc = client.upload_file("/not/exist.pdf")
except UnifilesError as e:
    print("操作失败:", e)
```

常见问题：
- 401/403：检查 `api_key` 是否正确、是否有权限访问资源。
- 404：`file_id`/`kb_id` 不存在或无权限；确认已创建并记录 ID。
- 429：请求过于频繁；增加重试退避或降低并发。
- 413/类型不支持：文件超过 100MB 或扩展名不在允许列表。
- 提取结果为空：确认 `mode` 与文档类型匹配；查看服务端日志。

---

## 与后端 API 的对应关系

- 文件上传：`POST /files`
- 内容提取：`POST /files/{file_id}/extract`
- 创建知识库：`POST /knowledge-bases`
- 文档索引：`POST /knowledge-bases/{kb_id}/documents`
- 知识库检索：`POST /knowledge-bases/{kb_id}/search`

详见：`docs/DEV/API_ENDPOINTS.md`

---

## 最佳实践

- 使用环境变量或密钥管理服务存储 `API Key`。
- 明确传入 `base_url`，与后端运行端口一致（默认 8088）。
- 对长耗时操作加入重试与轮询（如提取/索引）。
- 在生产中开启 HTTPS，限制密钥权限与有效期。
- 对批量任务优先使用幂等设计与断点续传策略。

---

## 参考

- 客户端实现：`unifiles/client/client.py`
- 包导出：`unifiles/client/__init__.py`
- API 端点：`docs/DEV/API_ENDPOINTS.md`
