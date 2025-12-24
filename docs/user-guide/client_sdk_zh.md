# Unifiles Python 客户端 SDK 用户指南

Unifiles Python 客户端 SDK 提供了一种简单而强大的方式来与 Unifiles 文档处理服务进行交互。它允许您轻松上传文件、提取内容 (OCR) 以及构建具有向量搜索功能的知识库。

## 安装

使用 pip 安装客户端 SDK：

```bash
pip install unifiles-client
```

## 快速开始

以下是一个完整的示例，帮助您快速上手。此脚本将上传一个文件，提取其内容，将其索引到知识库中，并执行搜索。

```python
from unifiles_client import Unifiles

# 1. 初始化客户端
client = Unifiles(
    api_key="your-api-key", 
    base_url="http://localhost:8088"
)

# 2. 创建知识库
kb = client.create_knowledge_base(
    name="My Knowledge Base", 
    description="A collection of important documents"
)
print(f"Created Knowledge Base: {kb.name} ({kb.kb_id})")

# 3. 上传、提取并索引文档
# 此辅助方法自动处理整个流程
document = kb.upload_document(
    file_path="path/to/your/document.pdf",
    auto_extract=True,
    auto_index=True
)
print(f"Document processed: {document.filename}")

# 4. 搜索知识库
# 仅文本检索
results = kb.search("What is the main topic of this document?", top_k=3)

print("\nSearch Results (Text Only):")
for result in results:
    print(f"- [{result.similarity_score:.3f}] {result.text_content[:100]}...")

# 文本 + 图片检索（包含图片组件）
image_results = kb.search(
    "What is shown in the diagrams?", top_k=3, include_photos=True
)

print("\nSearch Results (Text + Photos):")
for result in image_results:
    print(f"- [{result.similarity_score:.3f}] {result.text_content[:100]}...")
```

## 核心概念：三层架构

Unifiles 建立在“三层架构”之上，让您可以精细地控制文档的处理方式。

1.  **文件存储层 (File Storage Layer)**：
    *   **定义**：原始文件存储。
    *   **操作**：上传您的原始文件（PDF、图像、Office 文档等）。
    *   **结果**：一个带有 `file_id` 的 `Document` 对象。

2.  **内容提取层 (Content Extraction Layer)**：
    *   **定义**：将原始文件转换为机器可读文本和图像 (OCR) 的过程。
    *   **操作**：对文档调用 `extract_content()`。
    *   **结果**：文档获得“提取内容”（文本和 Markdown）。

3.  **知识库索引层 (Knowledge Base Indexing Layer)**：
    *   **定义**：智能层，内容在此处被分块、向量化并存储以供搜索。
    *   **操作**：对文档调用 `index_to_knowledge_base()`。
    *   **结果**：文档可在特定的 `KnowledgeBase` 中被搜索。

## 使用指南

### 1. 客户端初始化

首先，导入 `Unifiles` 并使用您的 API 密钥和服务器 URL 创建一个实例。

```python
from unifiles_client import Unifiles

client = Unifiles(api_key="your_api_key", base_url="http://localhost:8088")
```

### 2. 文件管理

您可以直接将文件上传到存储层，而无需立即处理它们。

```python
# 上传文件
doc = client.upload_file("contract.pdf")
print(f"Uploaded {doc.filename} (ID: {doc.file_id})")

# 列出所有文件
files = client.list_files(limit=10)
for f in files:
    print(f.filename)

# 删除文件
client.delete_file(doc.file_id)
```

### 3. 内容提取

为了使文件有用，您需要提取其内容。这是一个异步操作，但如果您要求，SDK 会为您处理等待。

```python
from unifiles_client import ContentType

# 上传
doc = client.upload_file("scan.png")

# 提取内容（等待完成）
task_result = doc.extract_content(mode="simple", wait=True)

# 推荐：使用 get_content() 辅助方法
text_content = doc.get_content(ContentType.TEXT)["content"]
print(text_content)
```

当 `wait=True` 时，`extract_content()` 返回来自 `/tasks/{task_id}/result` 的任务结果对象，并且 SDK 还会将提取的内容缓存在内部，以便之后可以使用 `get_content()`。

**提取模式：**
*   `simple`：使用默认 OCR / 解析管道的基本文本提取。
*   `selfhosted`：使用自托管 OCR / 多模态模型（需要服务器配置）。
*   `mistral`：使用基于 Mistral 的 LLM OCR/提取后端（需要配置）。
*   `openai`：使用兼容 OpenAI 的 OCR/提取后端（需要配置）。

所有模式都会经过同一个 OCR 提供者工厂；`simple` 现在是内置的 pdfplumber/PyMuPDF 提供者，只需切换名称即可走同一条流水线。

#### 图像内容解析（仅 selfhosted 模式）

当使用 `selfhosted` 模式时，可以通过 `parse_image_content` 参数控制是否为文档中的图片和表格生成语义化描述：

```python
# 基础提取 - 图片使用简单标签
doc = client.upload_file("report.pdf")
result = doc.extract_content(
    mode="selfhosted",
    parse_image_content=False,  # 默认值
    wait=True
)
# Markdown中: ![Picture](picture_1_0.png)

# 完整提取 - 图片使用AI生成的描述
result = doc.extract_content(
    mode="selfhosted",
    parse_image_content=True,  # 启用图像内容解析
    wait=True,
    timeout=600  # 建议增加超时时间
)
# Markdown中: ![产品外观设计图，展示了新款智能手机的三视图](picture_1_0.png)
```

**注意事项**：
- `parse_image_content` 仅在 `mode="selfhosted"` 时有效，其他模式会被忽略
- 为每张图片/表格生成描述会增加处理时间（约2-3倍）和API调用成本（约2-3倍）
- 图像描述会使全文检索更准确，适合用于重要文档和知识库
- 如果在非 `selfhosted` 模式下设置 `parse_image_content=True`，SDK 会抛出 `ValueError`

**性能对比示例**：

```python
import time

doc = client.upload_file("document_with_images.pdf")

# 快速模式
start = time.time()
doc.extract_content(mode="selfhosted", parse_image_content=False, wait=True)
print(f"快速模式: {time.time() - start:.1f}秒")

# 完整模式
start = time.time()
doc.extract_content(mode="selfhosted", parse_image_content=True, wait=True)
print(f"完整模式: {time.time() - start:.1f}秒")
```

### 4. 知识库管理

知识库是您索引文档的容器。

```python
# 创建知识库
kb = client.create_knowledge_base("Finance Docs")

# 获取现有知识库
kb = client.get_knowledge_base("kb_12345")

# 列出知识库
kbs = client.list_knowledge_bases()
```

### 5. 索引和搜索

最常见的工作流程是将文档添加到知识库，然后进行搜索。

```python
# 将文档添加到知识库（处理上传 -> 提取 -> 索引）
doc = kb.upload_document("report.pdf")

# 搜索
results = kb.search("quarterly revenue", top_k=5)
for res in results:
    print(res.text_content)
```

### 6. 文档管理

#### 获取文档详情

检索特定文档的完整信息，包括完整的提取Markdown内容：

```python
# 获取知识库
kb = client.get_knowledge_base("kb_12345")

# 列出文档以查找ID
documents = kb.list_documents(limit=10)
doc_id = documents[0]["document_id"]

# 获取详细信息
detail = kb.get_document_detail(doc_id)

print(f"文档: {detail['original_filename']}")
print(f"文件大小: {detail['file_size']} 字节")
print(f"分块数: {detail['chunk_count']}")
print(f"状态: {detail['indexing_status']}")

# 访问完整的Markdown内容
markdown = detail["markdown_content"]
print(f"内容预览: {markdown[:200]}...")

# 检查提取元数据
metadata = detail.get("extraction_metadata", {})
print(f"总页数: {metadata.get('total_pages')}")
print(f"总字符数: {metadata.get('total_chars')}")
```

**使用场景：**
- 检索完整提取文本用于显示或导出
- 检查索引状态和分块数量
- 访问文件元数据（原始文件名、大小）
- 调试提取质量

## 服务端接口说明 (v1.1.0)

- 提取使用 `POST /extractions/{file_id}` 与 `GET /extractions/{file_id}`；`/files/{file_id}/extract` 为计划中接口。
- 知识库详情 `GET /knowledge-bases/{kb_id}` 为计划中接口（当前返回 501）。
- 文档删除 `DELETE /knowledge-bases/{kb_id}/documents/{doc_id}` 为计划中接口（当前返回 501）。

## API 参考

### `Unifiles` 客户端

主要的 SDK 入口点是 `Unifiles` 类（从 `unifiles_client` 包导出）：

```python
from unifiles_client import Unifiles
```

主要方法：

*   `upload_file(file_path, is_public=False) -> Document`：将文件上传到存储层。
*   `get_document(file_id) -> Document`：通过 ID 获取 `Document` 实例。
*   `list_files(limit=50, offset=0) -> List[Document]`：列出当前用户的已上传文件。
*   `delete_file(file_id) -> bool`：删除文件；成功时返回 `True`。
*   `create_knowledge_base(name, description="") -> KnowledgeBase`：创建一个新的 `KnowledgeBase`。
*   `get_knowledge_base(kb_id) -> KnowledgeBase`：通过 ID 获取 `KnowledgeBase` 实例（需要时延迟加载信息）。（计划中接口；`GET /knowledge-bases/{kb_id}` 当前返回 501）。
*   `list_knowledge_bases(limit=50, offset=0) -> List[KnowledgeBase]`：列出当前用户的知识库。
*   `delete_knowledge_base(kb_id) -> bool`：删除知识库；成功时返回 `True`。
*   `quick_process(file_path, knowledge_base_name=None, extract_mode="simple") -> Document`：
    便捷辅助方法，用于上传文件、触发提取，并（可选）索引到指定的知识库中。

### `Document` 类

表示单个文件及其处理状态。

*   `extract_content(mode="simple", parse_image_content=False, wait=False, timeout=300, poll_interval=5)`：
    启动 OCR/内容提取过程。
    - `mode`：提取模式（simple|selfhosted|mistral|openai）
    - `parse_image_content`：是否解析图像内容到full_markdown（仅selfhosted模式有效，默认False）
    - `wait`：是否等待任务完成（默认False）
    - `timeout`：等待超时时间（秒）
    - `poll_interval`：轮询间隔（秒）
    
    当 `wait=True` 时，它会等待完成并返回来自 `/tasks/{task_id}/result` 的任务结果，同时将提取的内容缓存在 `Document` 内部。
    
    **注意**：如果 `parse_image_content=True` 但 `mode != "selfhosted"`，会抛出 `ValueError`。

*   `get_content(content_type: Optional[ContentType] = None)`：返回提取的内容字典；可选地通过 `ContentType.TEXT` 或 `ContentType.IMAGE` 过滤文本/图像。
*   `index_to_knowledge_base(kb_id, chunk_strategy="markdown_hierarchical")`：使用指定的分块策略将提取的内容索引到知识库中。
*   `status`：返回当前状态的属性 (`UPLOADED`, `EXTRACTING`, `EXTRACTED`, `INDEXED`, `FAILED`)。

### `KnowledgeBase` 类

管理一组可搜索的文档。

*   `upload_document(file_path, is_public=False, auto_extract=True, auto_index=True, extract_mode="simple") -> Document`：
    一次性上传并处理文件的辅助方法（上传 → 提取 → 索引）。
*   `search(query, top_k=10, include_photos=False) -> List[SearchResult]`：在此知识库中执行语义搜索。
    - `query`：检索查询文本。
    - `top_k`：返回结果数量（1–100）。
    - `include_photos`：是否在结果中包含图片组件（`component_type='photo'`），默认为 False。
*   `list_documents(limit=50, offset=0) -> List[Dict]`：
    列出此知识库中的文档。每个文档现在包含：
    - `document_id`、`extraction_id`、`knowledge_base_id`
    - `original_filename` - 原始文件名（新增）
    - `file_size` - 文件大小（字节）（新增）
    - `file_id` - 源文件ID（用于获取预览URL）（新增）
    - `chunk_count`、`indexing_status`、`created_at`
*   `get_document_detail(document_id) -> Dict`：
    检索特定文档的详细信息，包括：
    - 完整的Markdown内容（`markdown_content`）
    - 原始文件元数据（`original_filename`、`file_size`、`file_id`）
    - 索引状态和分块数量
    - 提取元数据（页数、字符数等）
*   `delete_document(document_id) -> bool`：从知识库中移除文档（需要服务器端点支持）。（计划中接口；当前返回 501）。
