# 数据类型

SDK 中的数据类型定义。

## 核心类型

### File

```python
@dataclass
class File:
    id: str                    # 文件唯一标识
    filename: str              # 原始文件名
    content_type: str          # MIME 类型
    size: int                  # 文件大小（字节）
    metadata: Dict[str, Any]   # 自定义元数据
    tags: List[str]            # 标签列表
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
```

### ExtractionJob

```python
@dataclass
class ExtractionJob:
    id: str                    # 提取任务 ID
    file_id: str               # 关联文件 ID
    status: str                # pending | processing | completed | failed
    mode: str                  # simple | normal | advanced
    progress: Optional[int]    # 进度 (0-100)
    markdown: Optional[str]    # 提取的 Markdown 内容
    total_pages: Optional[int] # 文档总页数
    metadata: Optional[Dict]   # 文档元信息
    error: Optional[Dict]      # 错误信息
    created_at: datetime
    completed_at: Optional[datetime]

    def wait(self, timeout: int = 300) -> "ExtractionJob": ...
```

### KnowledgeBase

```python
@dataclass
class KnowledgeBase:
    id: str
    name: str
    description: Optional[str]
    chunking_strategy: Dict[str, Any]
    document_count: int
    chunk_count: int
    metadata: Optional[Dict]
    created_at: datetime
    updated_at: datetime
```

### IndexedDocument

```python
@dataclass
class IndexedDocument:
    id: str
    kb_id: str
    file_id: str
    title: Optional[str]
    status: str                # pending | indexing | indexed | failed
    chunk_count: int
    metadata: Optional[Dict]
    error: Optional[Dict]
    created_at: datetime
    indexed_at: Optional[datetime]

    def wait(self, timeout: int = 300) -> "IndexedDocument": ...
```

### Chunk

```python
@dataclass
class Chunk:
    id: str
    document_id: str
    document_title: str
    content: str
    score: float               # 相似度分数 (0-1)
    vector_score: Optional[float]   # 向量搜索分数
    keyword_score: Optional[float]  # 关键词搜索分数
    metadata: Dict[str, Any]
```

### Webhook

```python
@dataclass
class Webhook:
    id: str
    url: str
    events: List[str]
    enabled: bool
    last_delivery_at: Optional[datetime]
    created_at: datetime
```

### APIKey

```python
@dataclass
class APIKey:
    id: str
    name: str
    key: Optional[str]         # 仅创建时返回
    key_prefix: str
    scopes: List[str]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
```

## 列表类型

```python
@dataclass
class ListResponse(Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int

# 具体类型
FileList = ListResponse[File]
ExtractionJobList = ListResponse[ExtractionJob]
KnowledgeBaseList = ListResponse[KnowledgeBase]
IndexedDocumentList = ListResponse[IndexedDocument]
```

## 搜索结果

```python
@dataclass
class SearchResults:
    query: str
    chunks: List[Chunk]
    total: int
```

## 使用统计

```python
@dataclass
class UsageStats:
    storage: StorageUsage
    extraction: ExtractionUsage
    knowledge_bases: KBUsage
    
@dataclass
class StorageUsage:
    used_bytes: int
    limit_bytes: int
    used_percentage: float

@dataclass  
class ExtractionUsage:
    pages_used: int
    pages_limit: int
    reset_at: datetime
```

## 类型导入

```python
from unifiles import (
    File,
    ExtractionJob,
    KnowledgeBase,
    IndexedDocument,
    Chunk,
    Webhook,
    APIKey,
    SearchResults,
    UsageStats
)
```
