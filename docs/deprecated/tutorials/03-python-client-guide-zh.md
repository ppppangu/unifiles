# Unifiles Python 客户端调用指南
本指南基于当前客户端代码（`unifiles/client/client.py`）编写，完全对齐服务端实现（FastAPI，端口 `8088`）。涵盖初始化、文件上传、内容提取（异步任务）、知识库索引与检索、快速流程、错误处理与支持文件类型等。

> 适用版本：客户端 `0.0.1`，服务端 `1.1.0`

---

## 1. 前提条件

- 运行中的服务端：`http://localhost:8088`（默认）
- Python 3.9+（建议）
- 可用的 API Key（通过服务端用户与访问密钥接口创建）

---

## 2. 安装与导入

推荐直接在源码仓库中使用（无需安装）：

```python
from unifiles.client import Unifile, Document, KnowledgeBase, ContentType, UnifilesError
```

如需打包安装，请参考仓库根目录的 `pyproject.toml`（本文不展开）。

---

## 3. 初始化客户端

```python
from unifiles.client import Unifile

# base_url 默认即为 http://localhost:8088
client = Unifile(api_key="sk_your_token", base_url="http://localhost:8088")
print(client.base_url)  # http://localhost:8088
```

---

## 4. 文件上传（第一层）

```python
from pathlib import Path

doc = client.upload_file(Path("./document.pdf"), is_public=False)
print(doc.file_id, doc.filename, doc.file_size, doc.status.value)
# 返回 Document 对象，初始状态通常为 uploaded
```

说明：
- `is_public` 会被正确编码为小写字符串 `true/false` 作为查询参数。
- 客户端在上传前会进行文件类型与大小校验（见「支持文件类型」）。

---

## 5. 内容提取（第二层，异步任务）

服务端的提取是「异步任务」：
- `POST /files/{file_id}/extract` 返回任务信息（`task_id`, `status`）。
- 最终结果通过 `GET /tasks/{task_id}/result` 获取。

客户端提供两种用法：

1) 直接等待完成（最简单）

```python
# 等待提取完成，并返回最终结果（包含 extracted_content）
result = doc.extract_content(mode="simple", wait=True)
extracted = result.get("extracted_content", {})
print("extraction_id=", extracted.get("extraction_id"))
```

2) 先提交任务，后轮询等待

```python
submit = doc.extract_content(mode="simple", wait=False)
print("task_id=", submit.get("task_id"), "status=", submit.get("status"))

# 轮询等待（默认 timeout=300s, poll_interval=5s）
doc.wait_for_extraction(timeout=300, poll_interval=5)

# 获取缓存的提取结果
content = doc.get_content()  # 若未完成会抛出 UnifilesError
print(content.get("extraction_id"))
print((content.get("extracted_text") or "")[:200])
```

提取模式：
- `simple`（默认，pdfplumber 简单文本）
- `mistral` / `selfhosted` / `openai`（多模态 OCR）

内容按类型读取：

```python
from unifiles.client import ContentType

text_part = doc.get_content(ContentType.TEXT)      # {"type": "text", "content": ...}
image_part = doc.get_content(ContentType.IMAGE)    # {"type": "image", "content": markdown}
```

---

## 6. 索引到知识库（第三层）

提取完成后可将文档索引至知识库：

```python
# 先创建或获取知识库
kb = client.create_knowledge_base("我的知识库", description="示例")

# 索引（默认分块策略：markdown_hierarchical）
index_resp = doc.index_to_knowledge_base(kb.kb_id, chunk_strategy="markdown_hierarchical")
print(index_resp.get("document", {}))
```

说明：
- `index_to_knowledge_base` 需要 `extraction_id`，客户端会从 `doc.get_content()` 的缓存取得，因此若未等待提取完成会报错。
- 支持分块策略：`markdown_hierarchical`（默认）、`fixed`、`semantic`。

---

## 7. 知识库检索

```python
results = kb.search("安装 电气 设备", top_k=5)
for r in results:
    print(f"score={r.similarity_score:.3f}", r.text_content[:80])
```

说明：
- 检索前请确保已索引至少一个文档。
- `top_k` 取值范围 1–100。

注意：
- 端点 `GET /knowledge-bases/{kb_id}` 目前服务端返回 `501 Not Implemented`，`KnowledgeBase.get_info()` 可能失败；创建、列表、索引、检索等端点可正常使用。

---

## 8. 一键流程（上传 → 提取 → 索引）

```python
processed_doc = client.quick_process(
    file_path="./document.pdf",
    knowledge_base_name="演示知识库",
    extract_mode="simple",
)
```

`quick_process` 语义：
- 上传文件
- 等待提取完成
- 若提供了 `knowledge_base_name`：查找或创建知识库，并索引该文档

---

## 9. 文件与知识库的列表/删除

```python
# 文件列表
files = client.list_files(limit=20, offset=0)
for d in files:
    print(d.file_id, d.filename)

# 删除文件
client.delete_file(file_id)

# 知识库列表
kbs = client.list_knowledge_bases(limit=20, offset=0)
for kb in kbs:
    print(kb.kb_id, kb.name)

# 删除知识库（若服务端未实现会返回 False）
client.delete_knowledge_base("kb_xxx")
```

---

## 10. 支持的文件类型（与服务端对齐）

客户端会在本地进行扩展名预校验（失败会直接抛错）：

- 文档：`.doc` `.docx` `.ppt` `.pptx` `.xls` `.xlsx` `.odt` `.ods` `.odp` `.txt` `.rtf` `.md` `.html` `.htm` `.csv` `.tsv` `.xml`
- PDF：`.pdf`
- 图片：`.jpg` `.jpeg` `.png` `.tiff` `.tif` `.bmp`
- 代码：`.py` `.ipynb` `.js` `.json`

也可通过服务端 `GET /files/types` 动态获取。

大小限制：客户端内置上限 `100MB`，超限会抛出异常。

---

## 11. 错误处理

客户端异常层次：

- `UnifilesError`（基类）
- `AuthenticationError`（401）
- `RateLimitError`（429）

示例：

```python
from unifiles.client import UnifilesError, AuthenticationError, RateLimitError

try:
    doc = client.upload_file("./document.pdf")
    doc.extract_content(wait=True)
except AuthenticationError:
    print("认证失败：请检查 API Key")
except RateLimitError:
    print("超出频率限制，请稍后重试")
except UnifilesError as e:
    print("客户端错误：", e)
```

---

## 12. 端到端示例

```python
from pathlib import Path
from unifiles.client import Unifile

client = Unifile(api_key="sk_xxx", base_url="http://localhost:8088")

# 1) 上传
doc = client.upload_file(Path("./demo.pdf"), is_public=False)

# 2) 提取（等待完成）
doc.extract_content(mode="simple", wait=True)

# 3) 创建知识库并索引
kb = client.create_knowledge_base("示例KB", "SDK演示")
doc.index_to_knowledge_base(kb.kb_id, chunk_strategy="markdown_hierarchical")

# 4) 检索
for item in kb.search("设备 安装", top_k=3):
    print(f"{item.similarity_score:.3f}", item.text_content[:80])
```

---

## 13. 常见问题

- `get_info()` 与 `get_knowledge_base(kb_id).get_info()`
  - `GET /knowledge-bases/{kb_id}` 服务端暂未实现（501），因此 `KnowledgeBase.get_info()` 可能失败；文件的 `get_info()` 可正常使用。
- 提取长期无结果
  - 检查 Celery Worker 与任务队列；或增大 `timeout`，观察 `wait_for_extraction()` 的轮询日志。
- 选择提取模式
  - `simple` 性能快但只做文本；`mistral/selfhosted/openai` 用于复杂场景的多模态提取。

---

## 14. 参考

- 服务端 API 参考：`docs/DEV/API_ENDPOINTS.md`
- 端到端示例脚本：`test/test_sdk_upload.py`
- 架构与数据流：`docs/architecture/`

如需进一步的 SDK 能力（如动态读取支持类型、统一的任务工具函数等），可在 `Unifile` 上扩展轻量封装。
