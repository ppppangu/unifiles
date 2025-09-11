# Core Layer 架构设计

## 概述

Core层采用Pipeline模式 + 策略模式，实现文档处理流程的高度可扩展和可配置化。

## 核心架构层次

```
server/core/
├── pipeline/           # Pipeline 核心
├── processors/         # 各种处理器
├── strategies/         # 策略实现
├── models/            # 数据模型
├── storage/           # 存储抽象
├── embedding/         # 嵌入模块
├── exceptions/        # 异常定义
└── utils/             # 工具类
```

## 1. Pipeline 核心架构

### 1.1 DocumentProcessor (主控制器)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum

class ProcessingMode(Enum):
    SIMPLE = "simple"
    NORMAL = "normal" 
    ADVANCED = "advanced"

class DocumentProcessor:
    """文档处理主控制器"""
    
    def __init__(self):
        self.stages: List[ProcessingStage] = []
        self.status_tracker: StatusTracker = StatusTracker()
        
    def add_stage(self, stage: ProcessingStage) -> 'DocumentProcessor':
        """添加处理阶段"""
        self.stages.append(stage)
        return self
        
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """执行完整处理流程"""
        try:
            for stage in self.stages:
                context = await stage.process(context)
                await self.status_tracker.update_status(
                    context.document_id, 
                    stage.get_stage_name(), 
                    ProcessingStatus.COMPLETED
                )
            
            return ProcessingResult(
                success=True,
                context=context,
                message="Processing completed successfully"
            )
            
        except ProcessingException as e:
            await self.status_tracker.update_status(
                context.document_id,
                e.stage_name,
                ProcessingStatus.FAILED,
                error=str(e)
            )
            raise
```

### 1.2 ProcessingStage (阶段抽象)

```python
class ProcessingStage(ABC):
    """处理阶段抽象基类"""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """处理当前阶段"""
        pass
        
    @abstractmethod
    def get_stage_name(self) -> str:
        """获取阶段名称"""
        pass
        
    @abstractmethod
    def can_retry(self) -> bool:
        """是否支持重试"""
        pass
```

### 1.3 ProcessingContext (处理上下文)

```python
@dataclass
class ProcessingContext:
    """处理上下文，贯穿整个pipeline"""
    
    # 基本信息
    document_id: str
    file_id: str
    user_id: str
    knowledge_base_id: str
    mode: ProcessingMode
    
    # 文件信息
    original_file_path: str
    original_filename: str
    content_type: str
    file_size: int
    
    # 处理过程中的中间产物
    pdf_path: Optional[str] = None
    markdown_content: Optional[str] = None
    markdown_path: Optional[str] = None
    extracted_images: List[str] = field(default_factory=list)
    
    # 分块结果
    text_chunks: List[TextChunk] = field(default_factory=list)
    image_chunks: List[ImageChunk] = field(default_factory=list)
    
    # 嵌入结果
    embeddings: List[EmbeddingResult] = field(default_factory=list)
    
    # 存储URL
    original_file_url: Optional[str] = None
    pdf_url: Optional[str] = None
    markdown_url: Optional[str] = None
    
    # 处理配置
    processing_config: Dict[str, Any] = field(default_factory=dict)
    
    # 处理日志
    processing_logs: List[ProcessingLog] = field(default_factory=list)
    
    def add_log(self, level: str, message: str, stage: str = None):
        """添加处理日志"""
        self.processing_logs.append(ProcessingLog(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            stage=stage or "unknown"
        ))
```

## 2. 具体处理器设计

### 2.1 FileConversionStage (格式转换阶段)

```python
class FileConversionStage(ProcessingStage):
    """文件格式转换阶段"""
    
    def __init__(self, converter_factory: ConverterFactory):
        super().__init__("file_conversion")
        self.converter_factory = converter_factory
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行格式转换"""
        context.add_log("INFO", f"开始转换文件: {context.original_filename}")
        
        # 获取合适的转换器
        converter = self.converter_factory.get_converter(context.content_type)
        
        # 执行转换
        pdf_path = await converter.convert_to_pdf(
            input_path=context.original_file_path,
            output_dir=self._get_temp_dir(context)
        )
        
        context.pdf_path = pdf_path
        context.add_log("INFO", f"PDF转换完成: {pdf_path}")
        
        return context
        
    def get_stage_name(self) -> str:
        return "file_conversion"
        
    def can_retry(self) -> bool:
        return True
```

### 2.2 OCRProcessingStage (OCR处理阶段)

```python
class OCRProcessingStage(ProcessingStage):
    """OCR处理阶段"""
    
    def __init__(self, 
                 ocr_processor: OCRProcessor,
                 storage_manager: StorageManager,
                 multimodal_processor: Optional[MultiModalProcessor] = None):
        super().__init__("ocr_processing")
        self.ocr_processor = ocr_processor
        self.storage_manager = storage_manager
        self.multimodal_processor = multimodal_processor
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行OCR处理"""
        context.add_log("INFO", "开始OCR处理")
        
        # 1. OCR处理
        ocr_result = await self.ocr_processor.process_pdf(context.pdf_path)
        context.markdown_content = ocr_result.markdown_content
        context.extracted_images = ocr_result.image_paths
        
        # 2. 多模态处理 (如果启用)
        if self.multimodal_processor and context.mode != ProcessingMode.SIMPLE:
            enhanced_content = await self.multimodal_processor.enhance_content(
                markdown_content=context.markdown_content,
                image_paths=context.extracted_images
            )
            context.markdown_content = enhanced_content.enhanced_markdown
            
        # 3. 存储处理结果
        await self._store_processing_results(context)
        
        context.add_log("INFO", "OCR处理完成")
        return context
        
    async def _store_processing_results(self, context: ProcessingContext):
        """存储处理结果"""
        # 保存markdown文件
        markdown_path = await self.storage_manager.save_markdown(
            content=context.markdown_content,
            document_id=context.document_id,
            user_id=context.user_id
        )
        context.markdown_path = markdown_path
        context.markdown_url = await self.storage_manager.get_public_url(markdown_path)
        
        # 上传PDF到持久化存储
        if context.pdf_path:
            pdf_storage_path = await self.storage_manager.upload_file(
                local_path=context.pdf_path,
                object_key=f"{context.user_id}/processed_files/{context.document_id}.pdf"
            )
            context.pdf_url = await self.storage_manager.get_public_url(pdf_storage_path)
```

### 2.3 ChunkingStage (分块处理阶段)

```python
class ChunkingStage(ProcessingStage):
    """分块处理阶段"""
    
    def __init__(self, chunking_strategy: ChunkingStrategy):
        super().__init__("chunking")
        self.chunking_strategy = chunking_strategy
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行分块处理"""
        context.add_log("INFO", "开始分块处理")
        
        # 执行分层分块
        chunking_result = await self.chunking_strategy.chunk_document(
            markdown_content=context.markdown_content,
            images=context.extracted_images,
            config=context.processing_config.get("chunking", {})
        )
        
        context.text_chunks = chunking_result.text_chunks
        context.image_chunks = chunking_result.image_chunks
        
        context.add_log("INFO", f"分块完成: {len(context.text_chunks)}个文本块, {len(context.image_chunks)}个图片块")
        
        return context
```

### 2.4 EmbeddingStage (嵌入处理阶段)

```python
class EmbeddingStage(ProcessingStage):
    """嵌入处理阶段"""
    
    def __init__(self, embedding_strategy: EmbeddingStrategy):
        super().__init__("embedding")
        self.embedding_strategy = embedding_strategy
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行嵌入处理"""
        context.add_log("INFO", "开始嵌入处理")
        
        # 处理文本块嵌入
        text_embeddings = []
        for chunk in context.text_chunks:
            embedding = await self.embedding_strategy.embed_text(chunk.content)
            text_embeddings.append(EmbeddingResult(
                chunk_id=chunk.chunk_id,
                chunk_type="text",
                embedding=embedding,
                metadata=chunk.metadata
            ))
            
        # 处理图像块嵌入 (如果支持)
        image_embeddings = []
        if self.embedding_strategy.supports_images():
            for chunk in context.image_chunks:
                embedding = await self.embedding_strategy.embed_image(chunk.image_path)
                image_embeddings.append(EmbeddingResult(
                    chunk_id=chunk.chunk_id,
                    chunk_type="image",
                    embedding=embedding,
                    metadata=chunk.metadata
                ))
        
        context.embeddings = text_embeddings + image_embeddings
        
        context.add_log("INFO", f"嵌入完成: {len(context.embeddings)}个向量")
        
        return context
```

## 3. 策略模式实现

### 3.1 转换策略

```python
class ConversionStrategy(ABC):
    """文件转换策略抽象"""
    
    @abstractmethod
    def can_convert(self, content_type: str) -> bool:
        pass
        
    @abstractmethod
    async def convert_to_pdf(self, input_path: str, output_dir: str) -> str:
        pass

class OfficeConversionStrategy(ConversionStrategy):
    """Office文档转换策略"""
    
    def can_convert(self, content_type: str) -> bool:
        return content_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]
```

### 3.2 分块策略

```python
class ChunkingStrategy(ABC):
    """分块策略抽象"""
    
    @abstractmethod
    async def chunk_document(self, 
                           markdown_content: str, 
                           images: List[str], 
                           config: Dict[str, Any]) -> ChunkingResult:
        pass

class HierarchicalChunkingStrategy(ChunkingStrategy):
    """分层分块策略"""
    
    async def chunk_document(self, markdown_content: str, images: List[str], config: Dict[str, Any]) -> ChunkingResult:
        # 第一层：markdown结构化分块
        primary_chunks = await self._primary_chunking(markdown_content)
        
        # 第二层：文本后处理分块
        final_text_chunks = []
        for chunk in primary_chunks:
            if chunk.chunk_type == "text":
                sub_chunks = await self._secondary_text_chunking(chunk, config)
                final_text_chunks.extend(sub_chunks)
            else:
                final_text_chunks.append(chunk)
        
        # 图片块处理
        image_chunks = await self._process_image_chunks(images, config)
        
        return ChunkingResult(
            text_chunks=final_text_chunks,
            image_chunks=image_chunks
        )
```

### 3.3 嵌入策略

```python
class EmbeddingStrategy(ABC):
    """嵌入策略抽象"""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        pass
        
    @abstractmethod
    def supports_images(self) -> bool:
        pass
        
    @abstractmethod
    async def embed_image(self, image_path: str) -> List[float]:
        pass

class OpenAIEmbeddingStrategy(EmbeddingStrategy):
    """OpenAI嵌入策略"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model = model
        
    async def embed_text(self, text: str) -> List[float]:
        # 调用OpenAI API
        pass
        
    def supports_images(self) -> bool:
        return False  # text-embedding-ada-002不支持图像
```

## 4. Pipeline 工厂

```python
class DocumentProcessorFactory:
    """文档处理器工厂"""
    
    @staticmethod
    def create_processor(mode: ProcessingMode, config: Dict[str, Any]) -> DocumentProcessor:
        """根据模式创建处理器"""
        processor = DocumentProcessor()
        
        # 格式转换阶段
        converter_factory = ConverterFactory()
        processor.add_stage(FileConversionStage(converter_factory))
        
        # OCR处理阶段
        ocr_processor = config.get("ocr_processor", DefaultOCRProcessor())
        storage_manager = config.get("storage_manager", MinIOStorageManager())
        multimodal_processor = None
        
        if mode != ProcessingMode.SIMPLE:
            multimodal_processor = config.get("multimodal_processor", DefaultMultiModalProcessor())
            
        processor.add_stage(OCRProcessingStage(
            ocr_processor=ocr_processor,
            storage_manager=storage_manager,
            multimodal_processor=multimodal_processor
        ))
        
        # 分块阶段
        chunking_strategy = config.get("chunking_strategy", HierarchicalChunkingStrategy())
        processor.add_stage(ChunkingStage(chunking_strategy))
        
        # 嵌入阶段
        embedding_strategy = config.get("embedding_strategy", OpenAIEmbeddingStrategy(
            api_key=config["openai_api_key"]
        ))
        processor.add_stage(EmbeddingStage(embedding_strategy))
        
        return processor
```

## 5. 状态管理

```python
class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

class StatusTracker:
    """状态跟踪器"""
    
    def __init__(self, db_session):
        self.db_session = db_session
        
    async def update_status(self, 
                          document_id: str, 
                          stage: str, 
                          status: ProcessingStatus,
                          progress: int = None,
                          error: str = None):
        """更新处理状态"""
        # 更新数据库中的状态
        pass
        
    async def get_status(self, document_id: str) -> Dict[str, Any]:
        """获取处理状态"""
        pass
```

这个架构设计的核心优势：

1. **高度可扩展**: 每个处理阶段都是独立的，可以轻松添加新的处理器
2. **策略模式**: 支持不同的转换、分块、嵌入策略，便于切换和扩展
3. **状态跟踪**: 完整的处理状态跟踪，支持错误恢复和重试
4. **配置驱动**: 通过配置可以灵活调整处理流程
5. **异步支持**: 全面支持异步处理，提高性能