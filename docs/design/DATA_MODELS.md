# Core Layer 数据建模

## 概述

定义Core层中所有实体类的数据结构，包括文档处理、分块、嵌入等各个环节涉及的数据模型。

## 1. 文档相关实体

### 1.1 Document (文档基本信息)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

@dataclass
class Document:
    """文档基本信息"""
    
    # 标识信息
    document_id: str
    file_id: str
    user_id: str
    knowledge_base_id: str
    
    # 文件信息
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    
    # 处理信息
    mode: ProcessingMode
    status: ProcessingStatus
    processing_progress: int = 0
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_completed(self) -> bool:
        return self.status == ProcessingStatus.COMPLETED
        
    def is_failed(self) -> bool:
        return self.status == ProcessingStatus.FAILED
        
    def can_retry(self) -> bool:
        return self.is_failed() and self.retry_count < self.max_retries
```

### 1.2 ProcessedDocument (处理后的文档)

```python
@dataclass
class ProcessedDocument(Document):
    """处理后的文档，包含所有处理结果"""
    
    # 文件URL
    original_file_url: Optional[str] = None
    pdf_url: Optional[str] = None
    markdown_url: Optional[str] = None
    
    # 处理结果统计
    total_chunks: int = 0
    text_chunks_count: int = 0
    image_chunks_count: int = 0
    embedding_count: int = 0
    
    # 处理日志
    processing_logs: List['ProcessingLog'] = field(default_factory=list)
    
    # 质量评估
    quality_score: Optional[float] = None
    confidence_score: Optional[float] = None
    
    def add_processing_log(self, level: str, message: str, stage: str = None):
        """添加处理日志"""
        self.processing_logs.append(ProcessingLog(
            document_id=self.document_id,
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            stage=stage or "unknown"
        ))
        
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取处理摘要"""
        return {
            "document_id": self.document_id,
            "status": self.status.value,
            "progress": self.processing_progress,
            "total_chunks": self.total_chunks,
            "text_chunks": self.text_chunks_count,
            "image_chunks": self.image_chunks_count,
            "embeddings": self.embedding_count,
            "quality_score": self.quality_score,
            "processing_time": (
                (self.completed_at - self.created_at).total_seconds() 
                if self.completed_at else None
            )
        }
```

### 1.3 KnowledgeBase (知识库)

```python
@dataclass
class KnowledgeBase:
    """知识库信息"""
    
    # 基本信息
    kb_id: str
    name: str
    description: Optional[str] = None
    user_id: str
    
    # 统计信息
    document_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_size: int = 0
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # 配置信息
    processing_config: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_statistics(self, documents: List[Document]):
        """更新统计信息"""
        self.document_count = len(documents)
        self.processing_count = sum(1 for d in documents if d.status == ProcessingStatus.PROCESSING)
        self.completed_count = sum(1 for d in documents if d.status == ProcessingStatus.COMPLETED)
        self.failed_count = sum(1 for d in documents if d.status == ProcessingStatus.FAILED)
        self.total_size = sum(d.file_size for d in documents)
        self.updated_at = datetime.utcnow()
```

## 2. 分块相关实体

### 2.1 BaseChunk (分块基类)

```python
@dataclass
class BaseChunk:
    """分块基类"""
    
    # 标识信息
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_type: str  # "text", "image", "table", "formula"
    
    # 位置信息
    page_number: Optional[int] = None
    position_info: Optional[Dict[str, Any]] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_unique_id(self) -> str:
        """获取唯一标识"""
        return f"{self.document_id}_{self.chunk_type}_{self.chunk_index}"
```

### 2.2 TextChunk (文本块)

```python
@dataclass
class TextChunk(BaseChunk):
    """文本分块"""
    
    # 文本内容
    content: str
    content_hash: str  # 内容哈希，用于去重
    
    # 文本统计
    char_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    
    # 结构信息
    heading_level: Optional[int] = None  # 标题级别
    parent_heading: Optional[str] = None  # 父级标题
    
    # 语义信息
    language: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    # 分块策略信息
    chunking_method: str = "hierarchical"
    overlap_with_previous: int = 0  # 与前一块的重叠字符数
    overlap_with_next: int = 0     # 与后一块的重叠字符数
    
    def __post_init__(self):
        super().__init__()
        self.chunk_type = "text"
        if not self.char_count:
            self.char_count = len(self.content)
        if not self.word_count:
            self.word_count = len(self.content.split())
        if not self.sentence_count:
            self.sentence_count = self.content.count('.') + self.content.count('!') + self.content.count('?')
```

### 2.3 ImageChunk (图片块)

```python
@dataclass
class ImageChunk(BaseChunk):
    """图片分块"""
    
    # 图片信息
    image_path: str
    image_url: Optional[str] = None
    image_hash: str  # 图片哈希
    
    # 图片属性
    width: int = 0
    height: int = 0
    format: Optional[str] = None  # PNG, JPEG, etc.
    size_bytes: int = 0
    
    # OCR信息
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    
    # 多模态描述
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    description: Optional[str] = None  # AI生成的详细描述
    
    # 分类信息
    image_type: Optional[str] = None  # "diagram", "chart", "photo", "screenshot"
    detected_objects: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__init__()
        self.chunk_type = "image"
```

### 2.4 ChunkingResult (分块结果)

```python
@dataclass
class ChunkingResult:
    """分块处理结果"""
    
    # 分块结果
    text_chunks: List[TextChunk] = field(default_factory=list)
    image_chunks: List[ImageChunk] = field(default_factory=list)
    
    # 统计信息
    total_chunks: int = 0
    processing_time: float = 0.0
    
    # 分块配置
    chunking_strategy: str = "hierarchical"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # 质量信息
    average_chunk_size: float = 0.0
    size_variance: float = 0.0
    
    def __post_init__(self):
        self.total_chunks = len(self.text_chunks) + len(self.image_chunks)
        if self.text_chunks:
            sizes = [chunk.char_count for chunk in self.text_chunks]
            self.average_chunk_size = sum(sizes) / len(sizes)
            mean_size = self.average_chunk_size
            self.size_variance = sum((size - mean_size) ** 2 for size in sizes) / len(sizes)
    
    def get_chunks_by_type(self, chunk_type: str) -> List[BaseChunk]:
        """按类型获取分块"""
        if chunk_type == "text":
            return self.text_chunks
        elif chunk_type == "image":
            return self.image_chunks
        else:
            return []
    
    def get_summary(self) -> Dict[str, Any]:
        """获取分块摘要"""
        return {
            "total_chunks": self.total_chunks,
            "text_chunks": len(self.text_chunks),
            "image_chunks": len(self.image_chunks),
            "average_chunk_size": self.average_chunk_size,
            "processing_time": self.processing_time,
            "chunking_strategy": self.chunking_strategy
        }
```

## 3. 嵌入相关实体

### 3.1 EmbeddingResult (嵌入结果)

```python
@dataclass
class EmbeddingResult:
    """嵌入处理结果"""
    
    # 标识信息
    embedding_id: str
    chunk_id: str
    document_id: str
    chunk_type: str
    
    # 嵌入向量
    embedding: List[float]
    embedding_dim: int
    
    # 嵌入配置
    model_name: str
    model_version: Optional[str] = None
    embedding_strategy: str = "openai"
    
    # 质量信息
    confidence_score: Optional[float] = None
    norm: Optional[float] = None  # 向量范数
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self.embedding_dim = len(self.embedding)
        if not self.norm:
            import math
            self.norm = math.sqrt(sum(x*x for x in self.embedding))
    
    def cosine_similarity(self, other: 'EmbeddingResult') -> float:
        """计算余弦相似度"""
        if self.embedding_dim != other.embedding_dim:
            raise ValueError("向量维度不匹配")
            
        dot_product = sum(a * b for a, b in zip(self.embedding, other.embedding))
        return dot_product / (self.norm * other.norm)
```

### 3.2 VectorRecord (向量数据库记录)

```python
@dataclass
class VectorRecord:
    """向量数据库记录"""
    
    # 基本信息
    vector_id: str
    document_id: str
    chunk_id: str
    knowledge_base_id: str
    
    # 向量信息
    embedding: List[float]
    embedding_model: str
    
    # 内容信息
    content: str  # 原始内容
    content_type: str  # text, image_caption, etc.
    content_hash: str
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 索引信息
    indexed: bool = False
    index_version: Optional[str] = None
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def to_vector_db_format(self) -> Dict[str, Any]:
        """转换为向量数据库格式"""
        return {
            "id": self.vector_id,
            "vector": self.embedding,
            "metadata": {
                "document_id": self.document_id,
                "chunk_id": self.chunk_id,
                "knowledge_base_id": self.knowledge_base_id,
                "content": self.content,
                "content_type": self.content_type,
                "content_hash": self.content_hash,
                "embedding_model": self.embedding_model,
                "created_at": self.created_at.isoformat(),
                **self.metadata
            }
        }
```

## 4. 处理相关实体

### 4.1 ProcessingLog (处理日志)

```python
@dataclass
class ProcessingLog:
    """处理日志"""
    
    # 标识信息
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    
    # 日志内容
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    message: str = ""
    stage: str = "unknown"
    
    # 详细信息
    details: Optional[Dict[str, Any]] = None
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # 性能信息
    duration_ms: Optional[float] = None
    memory_usage: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "log_id": self.log_id,
            "document_id": self.document_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "stage": self.stage,
            "details": self.details,
            "exception": self.exception,
            "duration_ms": self.duration_ms,
            "memory_usage": self.memory_usage
        }
```

### 4.2 ProcessingResult (处理结果)

```python
@dataclass
class ProcessingResult:
    """处理结果"""
    
    # 结果状态
    success: bool
    message: str
    
    # 处理上下文
    context: Optional['ProcessingContext'] = None
    
    # 时间信息
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    # 错误信息
    error: Optional[Exception] = None
    error_stage: Optional[str] = None
    
    # 结果数据
    data: Optional[Dict[str, Any]] = None
    
    def set_completed(self):
        """设置为完成状态"""
        self.end_time = datetime.utcnow()
        self.duration = (self.end_time - self.start_time).total_seconds()
    
    def set_failed(self, error: Exception, stage: str = None):
        """设置为失败状态"""
        self.success = False
        self.error = error
        self.error_stage = stage
        self.set_completed()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "message": self.message,
            "duration": self.duration,
            "error": str(self.error) if self.error else None,
            "error_stage": self.error_stage,
            "data": self.data
        }
```

### 4.3 OCRResult (OCR结果)

```python
@dataclass
class OCRResult:
    """OCR处理结果"""
    
    # 输入信息
    input_path: str
    input_type: str  # pdf, image
    
    # 输出结果
    markdown_content: str
    extracted_text: str
    image_paths: List[str] = field(default_factory=list)
    
    # 统计信息
    page_count: int = 0
    image_count: int = 0
    text_confidence: float = 0.0
    
    # 处理信息
    ocr_engine: str = "default"
    processing_time: float = 0.0
    
    # 质量评估
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取OCR摘要"""
        return {
            "page_count": self.page_count,
            "image_count": self.image_count,
            "text_length": len(self.extracted_text),
            "markdown_length": len(self.markdown_content),
            "text_confidence": self.text_confidence,
            "processing_time": self.processing_time,
            "ocr_engine": self.ocr_engine
        }
```

### 4.4 MultiModalResult (多模态处理结果)

```python
@dataclass
class MultiModalResult:
    """多模态处理结果"""
    
    # 输入信息
    original_markdown: str
    image_paths: List[str]
    
    # 输出结果
    enhanced_markdown: str
    image_descriptions: Dict[str, str] = field(default_factory=dict)
    image_captions: Dict[str, str] = field(default_factory=dict)
    
    # 处理信息
    model_name: str = "gpt-4-vision-preview"
    processing_time: float = 0.0
    
    # 质量信息
    enhancement_quality: Optional[float] = None
    description_confidence: Dict[str, float] = field(default_factory=dict)
    
    def get_total_enhancements(self) -> int:
        """获取总增强数量"""
        return len(self.image_descriptions) + len(self.image_captions)
```

## 5. 配置和异常

### 5.1 ProcessingConfig (处理配置)

```python
@dataclass
class ProcessingConfig:
    """处理配置"""
    
    # 基本配置
    mode: ProcessingMode = ProcessingMode.SIMPLE
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    timeout_seconds: int = 3600  # 1小时
    
    # OCR配置
    ocr_config: Dict[str, Any] = field(default_factory=dict)
    
    # 分块配置
    chunking_config: Dict[str, Any] = field(default_factory=lambda: {
        "strategy": "hierarchical",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "min_chunk_size": 100
    })
    
    # 嵌入配置
    embedding_config: Dict[str, Any] = field(default_factory=lambda: {
        "strategy": "openai",
        "model": "text-embedding-ada-002",
        "batch_size": 100
    })
    
    # 多模态配置
    multimodal_config: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "model": "gpt-4-vision-preview",
        "max_images": 20
    })
    
    # 存储配置
    storage_config: Dict[str, Any] = field(default_factory=dict)
    
    # 重试配置
    retry_config: Dict[str, Any] = field(default_factory=lambda: {
        "max_retries": 3,
        "retry_delay": 60,  # 秒
        "exponential_backoff": True
    })
    
    @classmethod
    def from_mode(cls, mode: ProcessingMode) -> 'ProcessingConfig':
        """根据处理模式创建配置"""
        config = cls(mode=mode)
        
        if mode == ProcessingMode.SIMPLE:
            config.multimodal_config["enabled"] = False
            config.chunking_config["chunk_size"] = 2000
        elif mode == ProcessingMode.NORMAL:
            config.multimodal_config["enabled"] = True
            config.chunking_config["chunk_size"] = 1000
        elif mode == ProcessingMode.ADVANCED:
            config.multimodal_config["enabled"] = True
            config.chunking_config["strategy"] = "adaptive"
            config.chunking_config["chunk_size"] = 500
            
        return config
```

### 5.2 ProcessingException (处理异常)

```python
class ProcessingException(Exception):
    """处理异常基类"""
    
    def __init__(self, message: str, stage: str = None, document_id: str = None, 
                 error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.document_id = document_id
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "stage": self.stage,
            "document_id": self.document_id,
            "error_code": self.error_code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }

class FileConversionException(ProcessingException):
    """文件转换异常"""
    pass

class OCRProcessingException(ProcessingException):
    """OCR处理异常"""
    pass

class ChunkingException(ProcessingException):
    """分块处理异常"""
    pass

class EmbeddingException(ProcessingException):
    """嵌入处理异常"""
    pass

class StorageException(ProcessingException):
    """存储异常"""
    pass
```

## 6. 枚举定义

```python
class ProcessingMode(Enum):
    """处理模式"""
    SIMPLE = "simple"      # 简单模式：仅OCR + 基础分块
    NORMAL = "normal"      # 普通模式：OCR + 多模态 + 分层分块
    ADVANCED = "advanced"  # 高级模式：全功能 + 自适应分块

class ProcessingStatus(Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ChunkType(Enum):
    """分块类型"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    FORMULA = "formula"
    CODE = "code"

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
```

这个数据建模设计的特点：

1. **完整性**: 覆盖了文档处理全流程的所有数据实体
2. **可扩展性**: 使用元数据字段支持未来扩展
3. **类型安全**: 使用dataclass和类型注解提供类型安全
4. **状态跟踪**: 完整的状态和日志跟踪支持
5. **质量评估**: 内置质量评估和统计信息
6. **灵活配置**: 支持多种配置模式和策略