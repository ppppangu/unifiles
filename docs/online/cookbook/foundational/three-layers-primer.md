# 三层架构入门

本教程深入讲解 Unifiles 的三层架构设计，帮助你理解各层的职责和它们如何协作。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                 Layer 3: 知识库 (Knowledge Base)            │
│         语义搜索、混合搜索、RAG 检索                          │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 索引
┌─────────────────────────────────────────────────────────────┐
│                 Layer 2: 内容提取 (Extraction)              │
│         OCR、格式转换、Markdown 输出                         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 解析
┌─────────────────────────────────────────────────────────────┐
│                 Layer 1: 文件存储 (Files)                   │
│         上传、存储、元数据管理                                │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ 上传
                         你的文档
```

## 为什么分三层？

### 传统方案的问题

```python
# 传统一体化方案
def process_document(file_path):
    # 上传 + 解析 + 索引 一步到位
    result = upload_and_process(file_path)
    return result.search("查询")

# 问题：
# 1. 无法只存储不解析
# 2. 无法只解析不索引
# 3. 无法复用已解析的内容
# 4. 无法对同一内容使用不同分块策略
```

### 三层解耦的好处

```python
# Layer 1: 只存储
file = client.files.upload("document.pdf")
# 可以只存储，不做其他处理

# Layer 2: 只提取（可选）
extraction = client.extractions.create(file_id=file.id)
# 可以只提取，不建知识库

# Layer 3: 只索引（可选）
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id
)
# 只有需要搜索时才索引
```

**灵活组合，按需使用。**

## Layer 1: 文件存储

### 职责

- 安全存储原始文件
- 管理文件元数据
- 提供文件访问接口

### 数据模型

```
File
├── id: string              # 唯一标识
├── filename: string        # 原始文件名
├── content_type: string    # MIME 类型
├── size: number            # 文件大小（字节）
├── metadata: object        # 自定义元数据
├── tags: string[]          # 标签
├── created_at: datetime    # 创建时间
└── storage_path: string    # 存储路径（内部）
```

### 操作示例

```python
# 上传文件
file = client.files.upload(
    path="contract.pdf",
    metadata={"project": "legal", "year": 2024},
    tags=["contract", "important"]
)

# 文件上传后的状态
print(file.id)           # file_abc123
print(file.filename)     # contract.pdf
print(file.size)         # 1048576 (1MB)
print(file.content_type) # application/pdf

# 列出文件
files = client.files.list(tags=["contract"])

# 下载文件
content = client.files.download(file.id)

# 删除文件
client.files.delete(file.id)
```

### 什么时候只用 Layer 1？

- **纯文件存储**：只需要安全存储，不需要处理
- **延迟处理**：先存储，稍后再提取
- **归档场景**：长期保存原始文件

## Layer 2: 内容提取

### 职责

- 解析各种文档格式
- OCR 识别扫描件
- 统一输出 Markdown

### 数据模型

```
Extraction
├── id: string              # 提取任务ID
├── file_id: string         # 关联的文件
├── status: string          # pending | processing | completed | failed
├── mode: string            # simple | normal | advanced
├── markdown: string        # 提取的 Markdown 内容
├── total_pages: number     # 文档页数
├── metadata: object        # 提取的元信息
├── created_at: datetime    # 创建时间
├── completed_at: datetime  # 完成时间
└── error: object           # 错误信息（如果失败）
```

### 操作示例

```python
# 创建提取任务
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal"
)

# 等待完成
extraction.wait()

# 获取结果
print(extraction.status)      # completed
print(extraction.total_pages) # 15
print(extraction.markdown[:500])  # Markdown 内容预览

# 提取完成后，文件和提取结果的关系
#
# file_abc123 (文件)
#     └── ext_xyz789 (提取结果)
#             └── "# 文档标题\n\n正文内容..." (Markdown)
```

### 什么时候只用 Layer 1 + Layer 2？

- **内容预览**：提取并展示文档内容
- **格式转换**：将各种格式转为 Markdown
- **数据导出**：提取内容后导出到其他系统
- **不需要搜索**：只需要结构化内容，不需要语义检索

```python
# 示例：文档内容预览
file = client.files.upload("report.pdf")
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 显示给用户
display_markdown(extraction.markdown)
# 不需要建知识库
```

## Layer 3: 知识库

### 职责

- 文档分块
- 向量嵌入
- 语义搜索

### 数据模型

```
Knowledge Base
├── id: string
├── name: string
├── description: string
├── chunking_strategy: object
├── document_count: number
├── chunk_count: number
└── created_at: datetime

Document (知识库中的文档引用)
├── id: string
├── kb_id: string           # 所属知识库
├── file_id: string         # 关联的文件
├── title: string
├── status: string          # pending | indexing | indexed | failed
├── chunk_count: number
├── metadata: object
└── created_at: datetime

Chunk (分块)
├── id: string
├── document_id: string
├── content: string         # 分块内容
├── embedding: vector       # 向量嵌入
├── metadata: object        # 页码、位置等
└── created_at: datetime
```

### 操作示例

```python
# 创建知识库
kb = client.knowledge_bases.create(
    name="company-docs",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512
    }
)

# 添加文档（需要先完成提取）
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id,
    title="公司手册"
)
doc.wait()  # 等待索引完成

# 搜索
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="年假政策是什么？",
    top_k=5
)

for chunk in results.chunks:
    print(f"相关度: {chunk.score:.2f}")
    print(f"内容: {chunk.content}")
```

### 一个文件，多个知识库

同一个文件可以添加到多个知识库，使用不同的分块策略：

```python
# 同一个文件
file = client.files.upload("handbook.pdf")
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 知识库1：细粒度分块，适合精确问答
kb_qa = client.knowledge_bases.create(
    name="qa-kb",
    chunking_strategy={"type": "fixed", "chunk_size": 256}
)
client.knowledge_bases.documents.create(kb_id=kb_qa.id, file_id=file.id)

# 知识库2：大分块，适合摘要生成
kb_summary = client.knowledge_bases.create(
    name="summary-kb",
    chunking_strategy={"type": "semantic", "chunk_size": 1024}
)
client.knowledge_bases.documents.create(kb_id=kb_summary.id, file_id=file.id)

# 同一文件，不同用途
qa_results = client.knowledge_bases.search(kb_id=kb_qa.id, query="...")
summary_results = client.knowledge_bases.search(kb_id=kb_summary.id, query="...")
```

## 数据流示例

### 完整流程

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# ========== Layer 1: 文件存储 ==========
print("1. 上传文件...")
file = client.files.upload(
    path="company_policy.pdf",
    metadata={"department": "HR"}
)
print(f"   文件ID: {file.id}")

# ========== Layer 2: 内容提取 ==========
print("2. 提取内容...")
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal"
)
extraction.wait()
print(f"   提取ID: {extraction.id}")
print(f"   页数: {extraction.total_pages}")

# ========== Layer 3: 知识库 ==========
print("3. 构建知识库...")
kb = client.knowledge_bases.create(
    name="hr-docs",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512
    }
)

doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id
)
doc.wait()
print(f"   知识库ID: {kb.id}")
print(f"   分块数量: {doc.chunk_count}")

# ========== 搜索 ==========
print("4. 语义搜索...")
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="年假申请流程",
    top_k=3
)

for i, chunk in enumerate(results.chunks):
    print(f"\n   结果 {i+1} (相关度: {chunk.score:.2f}):")
    print(f"   {chunk.content[:100]}...")
```

### 数据关系图

```
                    ┌─────────────────┐
                    │   files 表      │
                    │   (Layer 1)     │
                    │                 │
                    │ id: file_abc123 │
                    │ filename: ...   │
                    │ size: ...       │
                    └────────┬────────┘
                             │
                             │ 1:N
                             ▼
                    ┌─────────────────┐
                    │ extractions 表  │
                    │   (Layer 2)     │
                    │                 │
                    │ id: ext_xyz789  │
                    │ file_id: ...    │
                    │ markdown: ...   │
                    └────────┬────────┘
                             │
                             │ 引用
                             ▼
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ knowledge_bases │ │   documents 表  │ │   chunks 表     │
│      表         │ │   (Layer 3)     │ │   (Layer 3)     │
│   (Layer 3)     │ │                 │ │                 │
│                 │ │ id: doc_001     │ │ id: chunk_001   │
│ id: kb_001      │◄│ kb_id: kb_001   │◄│ doc_id: doc_001 │
│ name: hr-docs   │ │ file_id: ...    │ │ content: ...    │
│ chunk_count: 42 │ │ chunk_count: 42 │ │ embedding: ...  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 职责边界

| 层级 | 你的职责 | Unifiles 处理 |
|-----|---------|--------------|
| Layer 1 | 提供文件、定义元数据 | 安全存储、去重、访问控制 |
| Layer 2 | 选择提取模式 | 格式解析、OCR、Markdown 转换 |
| Layer 3 | 定义分块策略、编写搜索查询 | 分块、向量化、索引、检索 |

## 常见问题

### Q: 可以跳过某一层吗？

**A:** Layer 1 是必需的，Layer 2 和 Layer 3 可以按需使用。

```python
# 只存储
file = client.files.upload("doc.pdf")  # ✅

# 只存储 + 提取
extraction = client.extractions.create(file_id=file.id)  # ✅

# 直接建知识库（需要先提取）
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id  # 如果文件未提取，会自动触发提取
)  # ✅ 内部会先完成提取
```

### Q: 提取结果会占用额外存储吗？

**A:** 会。提取的 Markdown 内容独立存储，但通常比原文件小很多。

### Q: 删除文件会影响知识库吗？

**A:** 删除文件会级联删除相关的提取结果和知识库文档。

```python
# 删除文件
client.files.delete(file_id)
# → 自动删除关联的 extractions
# → 自动删除关联的 documents 和 chunks
```

### Q: 可以更新已提取的内容吗？

**A:** 需要重新提取。上传新版本文件，创建新的提取任务。

```python
# 更新文档
new_file = client.files.upload("doc_v2.pdf")
extraction = client.extractions.create(file_id=new_file.id)
extraction.wait()

# 更新知识库中的文档
client.knowledge_bases.documents.delete(kb_id, old_doc_id)
client.knowledge_bases.documents.create(kb_id, new_file.id)
```

## 小结

三层架构的核心价值：

1. **解耦**：各层独立，按需使用
2. **复用**：一次提取，多处使用
3. **灵活**：同一内容，不同策略
4. **清晰**：职责分明，易于理解

## 下一步

现在你已经理解了三层架构，可以开始动手实践：

- [第一次上传](../basics/your-first-upload.md) - 实践 Layer 1
- [内容提取](../basics/extracting-content.md) - 实践 Layer 2
- [构建知识库](../basics/building-knowledge-base.md) - 实践 Layer 3
