# Knowledge Bases 命名空间

知识库管理和搜索操作。

## create

创建知识库。

```python
kb = client.knowledge_bases.create(
    name: str,
    description: str = None,
    chunking_strategy: dict = None,
    metadata: dict = None
) -> KnowledgeBase
```

### 示例

```python
kb = client.knowledge_bases.create(
    name="legal-docs",
    description="法律文档知识库",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)
```

---

## list / get / update / delete

```python
# 列出知识库
kbs = client.knowledge_bases.list(limit=50, offset=0)

# 获取详情
kb = client.knowledge_bases.get(kb_id)

# 更新
kb = client.knowledge_bases.update(kb_id, name="new-name")

# 删除
client.knowledge_bases.delete(kb_id)
```

---

## search

语义搜索。

```python
results = client.knowledge_bases.search(
    kb_id: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.0,
    filter: dict = None
) -> SearchResults
```

### 示例

```python
results = client.knowledge_bases.search(
    kb_id="kb_abc123",
    query="违约条款有哪些？",
    top_k=5,
    threshold=0.7,
    filter={"metadata.category": "contract"}
)

for chunk in results.chunks:
    print(f"[{chunk.score:.2f}] {chunk.content[:100]}...")
```

---

## hybrid_search

混合搜索。

```python
results = client.knowledge_bases.hybrid_search(
    kb_id: str,
    query: str,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    top_k: int = 5
) -> SearchResults
```

---

## Documents 子命名空间

### documents.create

添加文档到知识库。

```python
doc = client.knowledge_bases.documents.create(
    kb_id: str,
    file_id: str,
    title: str = None,
    metadata: dict = None
) -> IndexedDocument
```

### 示例

```python
doc = client.knowledge_bases.documents.create(
    kb_id="kb_abc123",
    file_id="file_xyz789",
    title="合同模板",
    metadata={"category": "contract"}
)

# 等待索引完成
doc = doc.wait(timeout=300)
print(f"分块数: {doc.chunk_count}")
```

### documents.list / get / delete

```python
# 列出文档
docs = client.knowledge_bases.documents.list(kb_id)

# 获取文档
doc = client.knowledge_bases.documents.get(kb_id, doc_id)

# 删除文档
client.knowledge_bases.documents.delete(kb_id, doc_id)
```

---

## 对象定义

```python
@dataclass
class KnowledgeBase:
    id: str
    name: str
    description: str
    chunking_strategy: dict
    document_count: int
    chunk_count: int
    created_at: datetime

@dataclass
class IndexedDocument:
    id: str
    kb_id: str
    file_id: str
    title: str
    status: str  # pending | indexing | indexed | failed
    chunk_count: int
    metadata: dict
    
    def wait(self, timeout: int = 300) -> "IndexedDocument": ...

@dataclass
class Chunk:
    id: str
    document_id: str
    document_title: str
    content: str
    score: float
    metadata: dict
```
