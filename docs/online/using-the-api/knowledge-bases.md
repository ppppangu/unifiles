# 知识库

知识库是 Unifiles 三层架构的第三层，负责将提取的内容组织、索引并提供语义搜索能力。这是构建 RAG（检索增强生成）应用的核心。

## 知识库概念

```
知识库 (Knowledge Base)
    └── 文档 (Documents)
            └── 分块 (Chunks)
                    └── 向量嵌入 (Embeddings)
```

- **知识库**：文档的逻辑集合，每个知识库可以有独立的分块策略和搜索配置
- **文档**：已提取内容的引用，一个文件可以添加到多个知识库
- **分块**：文档被切分成的语义单元，用于精确检索
- **嵌入**：分块的向量表示，支持语义相似度搜索

## SDK 使用

### 创建知识库

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

# 创建知识库
kb = client.knowledge_bases.create(
    name="legal-docs",
    description="法律文档知识库",
    chunking_strategy={
        "type": "semantic",      # fixed | semantic | paragraph
        "chunk_size": 512,       # 目标分块大小（token数）
        "overlap": 50            # 重叠token数
    },
    embedding_model="text-embedding-3-small"  # 可选，默认使用系统配置
)

print(f"知识库已创建: {kb.id}")
print(f"名称: {kb.name}")
```

### 列出知识库

```python
# 获取所有知识库
kbs = client.knowledge_bases.list(limit=50)

for kb in kbs.items:
    print(f"{kb.id}: {kb.name}")
    print(f"  文档数: {kb.document_count}")
    print(f"  总分块: {kb.chunk_count}")
```

### 获取知识库详情

```python
kb = client.knowledge_bases.get(kb_id)

print(f"名称: {kb.name}")
print(f"描述: {kb.description}")
print(f"分块策略: {kb.chunking_strategy}")
print(f"文档数量: {kb.document_count}")
print(f"分块数量: {kb.chunk_count}")
print(f"创建时间: {kb.created_at}")
```

### 更新知识库

```python
kb = client.knowledge_bases.update(
    kb_id=kb.id,
    name="legal-docs-v2",
    description="更新后的描述"
)
```

### 删除知识库

```python
# 删除知识库（会删除所有关联的文档和分块）
client.knowledge_bases.delete(kb_id)
```

## 文档管理

### 添加文档到知识库

```python
# 添加已提取的文件到知识库
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id,              # 必须是已完成提取的文件
    title="合同模板v2.0",          # 可选，自定义标题
    metadata={                     # 可选，自定义元数据
        "category": "contract",
        "version": "2.0",
        "department": "legal"
    }
)

print(f"文档已添加: {doc.id}")
print(f"状态: {doc.status}")  # pending -> indexing -> indexed
```

### 等待索引完成

```python
# 等待文档索引完成
doc = doc.wait(timeout=300)

if doc.status == "indexed":
    print(f"索引完成！")
    print(f"分块数量: {doc.chunk_count}")
else:
    print(f"索引失败: {doc.error}")
```

### 列出知识库中的文档

```python
docs = client.knowledge_bases.documents.list(
    kb_id=kb.id,
    limit=50
)

for doc in docs.items:
    print(f"{doc.id}: {doc.title}")
    print(f"  状态: {doc.status}")
    print(f"  分块数: {doc.chunk_count}")
```

### 获取文档详情

```python
doc = client.knowledge_bases.documents.get(
    kb_id=kb.id,
    document_id=doc.id
)

print(f"标题: {doc.title}")
print(f"文件ID: {doc.file_id}")
print(f"分块数: {doc.chunk_count}")
print(f"元数据: {doc.metadata}")
```

### 删除文档

```python
# 从知识库中移除文档（不会删除原文件）
client.knowledge_bases.documents.delete(
    kb_id=kb.id,
    document_id=doc.id
)
```

## 搜索

### 语义搜索

语义搜索使用向量相似度匹配，理解查询的语义而非仅仅关键词：

```python
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="违约条款有哪些？",
    top_k=5,                    # 返回最相关的5个结果
    threshold=0.7               # 相似度阈值（0-1）
)

print(f"找到 {len(results.chunks)} 个相关片段")

for chunk in results.chunks:
    print(f"\n相似度: {chunk.score:.2f}")
    print(f"来源: {chunk.document_title}")
    print(f"内容: {chunk.content[:200]}...")
```

### 混合搜索

结合语义搜索和关键词搜索，提高召回率：

```python
results = client.knowledge_bases.hybrid_search(
    kb_id=kb.id,
    query="违约金计算方法",
    vector_weight=0.7,          # 语义搜索权重
    keyword_weight=0.3,         # 关键词搜索权重
    top_k=10
)

for chunk in results.chunks:
    print(f"综合得分: {chunk.score:.2f}")
    print(f"语义得分: {chunk.vector_score:.2f}")
    print(f"关键词得分: {chunk.keyword_score:.2f}")
    print(f"内容: {chunk.content[:200]}...")
```

### 带过滤的搜索

使用元数据过滤搜索结果：

```python
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="合同条款",
    top_k=10,
    filter={
        "metadata.category": "contract",
        "metadata.version": {"$gte": "2.0"}
    }
)
```

**支持的过滤操作符：**

| 操作符 | 说明 | 示例 |
|-------|------|------|
| `$eq` | 等于（默认） | `{"field": "value"}` |
| `$ne` | 不等于 | `{"field": {"$ne": "value"}}` |
| `$gt` | 大于 | `{"field": {"$gt": 10}}` |
| `$gte` | 大于等于 | `{"field": {"$gte": 10}}` |
| `$lt` | 小于 | `{"field": {"$lt": 10}}` |
| `$lte` | 小于等于 | `{"field": {"$lte": 10}}` |
| `$in` | 在列表中 | `{"field": {"$in": ["a", "b"]}}` |

## REST API

### 知识库操作

**创建知识库：**

```http
POST /v1/knowledge-bases
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "name": "legal-docs",
    "description": "法律文档知识库",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
}
```

**响应：**

```json
{
    "id": "kb_abc123",
    "name": "legal-docs",
    "description": "法律文档知识库",
    "chunking_strategy": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    },
    "document_count": 0,
    "chunk_count": 0,
    "created_at": "2024-01-15T10:30:00Z"
}
```

**列出知识库：**

```http
GET /v1/knowledge-bases?limit=50&offset=0
Authorization: Bearer <api-key>
```

**获取知识库：**

```http
GET /v1/knowledge-bases/{kb_id}
Authorization: Bearer <api-key>
```

**更新知识库：**

```http
PATCH /v1/knowledge-bases/{kb_id}
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "name": "legal-docs-v2",
    "description": "更新后的描述"
}
```

**删除知识库：**

```http
DELETE /v1/knowledge-bases/{kb_id}
Authorization: Bearer <api-key>
```

### 文档操作

**添加文档：**

```http
POST /v1/knowledge-bases/{kb_id}/documents
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "file_id": "file_xyz789",
    "title": "合同模板v2.0",
    "metadata": {
        "category": "contract"
    }
}
```

**响应：**

```json
{
    "id": "doc_def456",
    "kb_id": "kb_abc123",
    "file_id": "file_xyz789",
    "title": "合同模板v2.0",
    "status": "pending",
    "metadata": {
        "category": "contract"
    },
    "created_at": "2024-01-15T10:35:00Z"
}
```

**列出文档：**

```http
GET /v1/knowledge-bases/{kb_id}/documents?limit=50
Authorization: Bearer <api-key>
```

**获取文档：**

```http
GET /v1/knowledge-bases/{kb_id}/documents/{document_id}
Authorization: Bearer <api-key>
```

**删除文档：**

```http
DELETE /v1/knowledge-bases/{kb_id}/documents/{document_id}
Authorization: Bearer <api-key>
```

### 搜索操作

**语义搜索：**

```http
POST /v1/knowledge-bases/{kb_id}/search
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "query": "违约条款有哪些？",
    "top_k": 5,
    "threshold": 0.7
}
```

**响应：**

```json
{
    "query": "违约条款有哪些？",
    "chunks": [
        {
            "id": "chunk_001",
            "document_id": "doc_def456",
            "document_title": "合同模板v2.0",
            "content": "第十条 违约责任\n\n1. 甲方违约...",
            "score": 0.92,
            "metadata": {
                "page": 5,
                "section": "第十条"
            }
        }
    ],
    "total": 1
}
```

**混合搜索：**

```http
POST /v1/knowledge-bases/{kb_id}/hybrid-search
Authorization: Bearer <api-key>
Content-Type: application/json

{
    "query": "违约金计算方法",
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "top_k": 10
}
```

## 分块策略

选择合适的分块策略对 RAG 效果至关重要。

### fixed（固定大小分块）

按固定 token 数切分，简单高效：

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "fixed",
        "chunk_size": 512,    # 每块512 tokens
        "overlap": 50         # 重叠50 tokens
    }
)
```

**适用场景：**

- 结构不规则的文档
- 需要快速索引
- 对精确边界要求不高

### semantic（语义分块）

基于语义边界智能切分：

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)
```

**适用场景：**

- 结构化文档（合同、论文）
- 需要保持语义完整性
- 对搜索质量要求高

### paragraph（段落分块）

按段落边界切分：

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "paragraph",
        "max_chunk_size": 1024,   # 最大块大小
        "min_chunk_size": 100     # 最小块大小
    }
)
```

**适用场景：**

- 段落清晰的文档
- 需要保持段落完整
- 文档格式一致

### 分块策略对比

| 策略 | 速度 | 语义完整性 | 适用场景 |
|-----|------|-----------|---------|
| fixed | 最快 | 一般 | 大规模快速索引 |
| semantic | 中等 | 最好 | 高质量问答 |
| paragraph | 快 | 好 | 结构清晰的文档 |

## 搜索最佳实践

### 1. 选择合适的 top_k

```python
# 简单问答：较少结果
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="公司注册资本是多少？",
    top_k=3
)

# 复杂分析：更多结果
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="总结所有违约条款",
    top_k=10
)
```

### 2. 使用阈值过滤低相关结果

```python
# 高精度场景：较高阈值
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="具体条款",
    threshold=0.8  # 只返回高相关结果
)

# 广泛探索：较低阈值
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="相关内容",
    threshold=0.5  # 返回更多可能相关的结果
)
```

### 3. 混合搜索提高召回率

```python
# 当语义搜索可能遗漏关键词时，使用混合搜索
results = client.knowledge_bases.hybrid_search(
    kb_id=kb.id,
    query="ISO9001认证",  # 包含专有名词
    vector_weight=0.6,
    keyword_weight=0.4    # 提高关键词权重
)
```

### 4. 利用元数据过滤

```python
# 按部门过滤
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="审批流程",
    filter={"metadata.department": "finance"}
)

# 按时间范围过滤
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="政策变更",
    filter={
        "metadata.year": {"$gte": 2023}
    }
)
```

## 完整工作流示例

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

# 1. 创建知识库
kb = client.knowledge_bases.create(
    name="company-docs",
    description="公司文档知识库",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)

# 2. 上传并提取文件
files_to_process = ["policy.pdf", "handbook.docx", "faq.md"]

for path in files_to_process:
    # 上传
    file = client.files.upload(path)
    
    # 提取
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
    
    # 添加到知识库
    doc = client.knowledge_bases.documents.create(
        kb_id=kb.id,
        file_id=file.id
    )
    doc.wait()
    
    print(f"已处理: {path}")

# 3. 搜索
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="年假政策是什么？",
    top_k=5
)

# 4. 使用搜索结果（例如传给LLM）
context = "\n\n".join([
    f"【{chunk.document_title}】\n{chunk.content}"
    for chunk in results.chunks
])

print("检索到的上下文:")
print(context)
```

## 下一步

- [Webhooks](webhooks.md) - 配置索引完成等事件的通知
- [LangChain 集成](../integrations/langchain.md) - 将知识库接入 LangChain
- [分块策略详解](../cookbook/intermediate/chunking-strategies.md) - 深入了解分块优化
