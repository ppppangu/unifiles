# Core Layer 实施清单

## 概述

这个清单帮助确保Core层的所有组件都按照设计正确实现。按照清单顺序实施，每完成一项都应进行测试验证。

## 1. 基础设施搭建

### 1.1 目录结构创建

```bash
server/core/
├── __init__.py
├── pipeline/
│   ├── __init__.py
│   ├── document_processor.py      # 主控制器
│   ├── processing_stage.py        # 阶段抽象
│   └── status_tracker.py          # 状态跟踪
├── processors/
│   ├── __init__.py
│   ├── file_converter.py          # 文件转换
│   ├── ocr_processor.py           # OCR处理
│   ├── multimodal_processor.py    # 多模态处理
│   └── chunking_processor.py      # 分块处理
├── strategies/
│   ├── __init__.py
│   ├── conversion/
│   │   ├── __init__.py
│   │   ├── base.py               # 转换策略基类
│   │   ├── office_converter.py   # Office文档转换
│   │   ├── image_converter.py    # 图片转换
│   │   └── text_converter.py     # 文本转换
│   ├── chunking/
│   │   ├── __init__.py
│   │   ├── base.py               # 分块策略基类
│   │   ├── hierarchical.py       # 分层分块
│   │   ├── semantic.py           # 语义分块
│   │   └── adaptive.py           # 自适应分块
│   └── embedding/
│       ├── __init__.py
│       ├── base.py               # 嵌入策略基类
│       ├── openai_embedding.py   # OpenAI嵌入
│       └── huggingface_embedding.py # HuggingFace嵌入
├── models/
│   ├── __init__.py
│   ├── document.py               # 文档相关模型
│   ├── chunks.py                 # 分块相关模型
│   ├── embeddings.py             # 嵌入相关模型
│   ├── processing.py             # 处理相关模型
│   └── config.py                 # 配置模型
├── storage/
│   ├── __init__.py
│   ├── base.py                   # 存储抽象
│   ├── minio_storage.py          # MinIO存储
│   ├── vector_store.py           # 向量存储抽象
│   └── postgres_vector.py        # PostgreSQL向量存储
├── exceptions/
│   ├── __init__.py
│   └── processing_exceptions.py  # 处理异常
└── utils/
    ├── __init__.py
    ├── file_utils.py             # 文件工具
    ├── text_utils.py             # 文本工具
    └── metrics.py                # 性能指标
```

**验证**: 
- [ ] 目录结构创建完成
- [ ] 所有__init__.py文件创建
- [ ] 基础导入测试通过

### 1.2 依赖包安装

```bash
# 核心依赖
pip install asyncio aiofiles
pip install pydantic dataclasses-json
pip install sqlalchemy asyncpg
pip install minio
pip install openai tiktoken

# 文件处理依赖  
pip install python-docx python-pptx openpyxl
pip install Pillow pdf2image
pip install pypdf2 pdfplumber
pip install python-magic

# OCR依赖
pip install pytesseract easyocr
pip install opencv-python

# 向量处理依赖
pip install numpy scikit-learn
pip install faiss-cpu  # 或 faiss-gpu
```

**验证**:
- [ ] 所有依赖包安装成功
- [ ] 导入测试无异常

## 2. 数据模型实现

### 2.1 基础数据模型

**实施顺序**:
1. [ ] 实现枚举类 (`ProcessingMode`, `ProcessingStatus`, `ChunkType`)
2. [ ] 实现基础模型 (`Document`, `KnowledgeBase`)
3. [ ] 实现分块模型 (`BaseChunk`, `TextChunk`, `ImageChunk`)
4. [ ] 实现嵌入模型 (`EmbeddingResult`, `VectorRecord`)
5. [ ] 实现处理模型 (`ProcessingContext`, `ProcessingResult`)
6. [ ] 实现配置模型 (`ProcessingConfig`)
7. [ ] 实现异常类 (`ProcessingException`及其子类)

**验证**:
- [ ] 所有模型字段正确定义
- [ ] 类型注解完整
- [ ] 默认值设置合理
- [ ] 模型方法实现正确
- [ ] 序列化/反序列化测试通过

### 2.2 数据库模型

创建对应的SQLAlchemy模型:

```python
# server/core/models/database.py
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class DocumentModel(Base):
    __tablename__ = "documents"
    
    document_id = Column(String, primary_key=True)
    file_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    knowledge_base_id = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mode = Column(String, nullable=False)
    status = Column(String, nullable=False)
    processing_progress = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    metadata = Column(JSON, default={})
    
    # 处理结果
    original_file_url = Column(String)
    pdf_url = Column(String)
    markdown_url = Column(String)
    total_chunks = Column(Integer, default=0)
    text_chunks_count = Column(Integer, default=0)
    image_chunks_count = Column(Integer, default=0)
    embedding_count = Column(Integer, default=0)
    quality_score = Column(Float)
```

**验证**:
- [ ] 数据库模型创建
- [ ] 表结构设计合理
- [ ] 索引添加适当
- [ ] 迁移脚本生成
- [ ] 数据库连接测试

## 3. 存储层实现

### 3.1 MinIO存储管理器

```python
# server/core/storage/minio_storage.py
from minio import Minio
from minio.error import S3Error

class MinIOStorageManager:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket_name: str):
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        self.bucket_name = bucket_name
        
    async def upload_content(self, content: bytes, object_key: str, content_type: str) -> str:
        """上传内容到MinIO"""
        # 实现上传逻辑
        pass
        
    async def get_public_url(self, object_key: str) -> str:
        """获取公共URL"""
        # 实现URL生成逻辑
        pass
```

**验证**:
- [ ] MinIO连接测试
- [ ] 文件上传功能
- [ ] URL生成功能
- [ ] 错误处理完善

### 3.2 向量存储实现

```python
# server/core/storage/postgres_vector.py
import asyncpg
import numpy as np

class PostgresVectorStore:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    async def upsert_vectors(self, vector_records: List[VectorRecord]):
        """批量插入/更新向量"""
        # 实现向量存储逻辑
        pass
        
    async def similarity_search(self, query_vector: List[float], top_k: int = 10):
        """相似度搜索"""
        # 实现搜索逻辑
        pass
```

**验证**:
- [ ] PostgreSQL + pgvector 扩展安装
- [ ] 向量表创建
- [ ] 向量插入功能
- [ ] 相似度搜索功能
- [ ] 性能测试

## 4. 处理器实现

### 4.1 文件转换器

**实施顺序**:
1. [ ] 实现转换策略基类 (`ConversionStrategy`)
2. [ ] 实现Office文档转换 (`OfficeConversionStrategy`)
3. [ ] 实现图片转换 (`ImageConversionStrategy`) 
4. [ ] 实现文本转换 (`TextConversionStrategy`)
5. [ ] 实现转换器工厂 (`ConverterFactory`)

**验证**:
- [ ] 各种格式转换测试
- [ ] 转换质量检查
- [ ] 异常处理测试
- [ ] 性能测试

### 4.2 OCR处理器

```python
# server/core/processors/ocr_processor.py
import pytesseract
from PIL import Image

class OCRProcessor:
    def __init__(self, ocr_engine: str = "tesseract"):
        self.ocr_engine = ocr_engine
        
    async def process_pdf(self, pdf_path: str, options: Dict = None) -> OCRResult:
        """处理PDF文件"""
        # 实现OCR逻辑
        pass
```

**验证**:
- [ ] PDF文本提取功能
- [ ] 图片识别功能
- [ ] Markdown格式输出
- [ ] 多语言支持
- [ ] 置信度评估

### 4.3 多模态处理器

```python
# server/core/processors/multimodal_processor.py
import openai

class MultiModalProcessor:
    def __init__(self, api_key: str, model: str = "gpt-4-vision-preview"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        
    async def enhance_content(self, markdown_content: str, image_paths: List[str]) -> MultiModalResult:
        """增强内容"""
        # 实现多模态处理逻辑
        pass
```

**验证**:
- [ ] 图片描述生成
- [ ] 内容增强功能
- [ ] API调用优化
- [ ] 错误处理
- [ ] 成本控制

## 5. 分块策略实现

### 5.1 分层分块策略

```python
# server/core/strategies/chunking/hierarchical.py
import re
from typing import List

class HierarchicalChunkingStrategy(ChunkingStrategy):
    async def chunk_document(self, markdown_content: str, images: List[str], config: Dict) -> ChunkingResult:
        """分层分块实现"""
        # 1. 第一层：按markdown结构分块
        primary_chunks = await self._primary_chunking(markdown_content)
        
        # 2. 第二层：文本后处理分块
        final_chunks = await self._secondary_chunking(primary_chunks, config)
        
        # 3. 图片块处理
        image_chunks = await self._process_images(images)
        
        return ChunkingResult(
            text_chunks=final_chunks,
            image_chunks=image_chunks
        )
```

**验证**:
- [ ] Markdown结构解析
- [ ] 标题层级识别
- [ ] 文本分块算法
- [ ] 重叠处理
- [ ] 分块质量评估

## 6. 嵌入策略实现

### 6.1 OpenAI嵌入策略

```python
# server/core/strategies/embedding/openai_embedding.py
import openai
import tiktoken

class OpenAIEmbeddingStrategy(EmbeddingStrategy):
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.tokenizer = tiktoken.encoding_for_model(model)
        
    async def embed_text(self, text: str) -> List[float]:
        """生成文本嵌入"""
        # 实现嵌入逻辑
        pass
```

**验证**:
- [ ] 文本嵌入功能
- [ ] Token限制处理
- [ ] 批量处理优化
- [ ] API配额管理
- [ ] 嵌入质量检查

## 7. Pipeline核心实现

### 7.1 处理阶段基类

```python
# server/core/pipeline/processing_stage.py
from abc import ABC, abstractmethod

class ProcessingStage(ABC):
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        pass
        
    @abstractmethod
    def get_stage_name(self) -> str:
        pass
        
    @abstractmethod
    def can_retry(self) -> bool:
        pass
```

**验证**:
- [ ] 抽象接口定义正确
- [ ] 各具体阶段实现
- [ ] 错误处理机制
- [ ] 重试逻辑

### 7.2 文档处理器主控制器

**实施要点**:
1. [ ] 实现Pipeline初始化逻辑
2. [ ] 实现阶段执行控制
3. [ ] 实现状态跟踪集成
4. [ ] 实现错误处理和恢复
5. [ ] 实现性能监控
6. [ ] 实现资源管理

**验证**:
- [ ] 完整流程测试
- [ ] 异常场景测试
- [ ] 性能基准测试
- [ ] 内存泄漏检查
- [ ] 并发处理测试

## 8. API集成

### 8.1 创建Core服务接口

```python
# server/core/service.py
from server.core.pipeline import DocumentProcessingPipeline
from server.core.models import ProcessingConfig, ProcessingMode

class DocumentProcessingService:
    def __init__(self, db_session, storage_manager, config_manager):
        self.db_session = db_session
        self.storage_manager = storage_manager
        self.config_manager = config_manager
        
    async def start_document_processing(self, 
                                      file_path: str,
                                      document_id: str,
                                      user_id: str, 
                                      knowledge_base_id: str,
                                      mode: ProcessingMode) -> ProcessingResult:
        """启动文档处理"""
        # 获取配置
        config = await self.config_manager.get_processing_config(user_id, mode)
        
        # 创建pipeline
        pipeline = DocumentProcessingPipeline(
            db_session=self.db_session,
            storage_manager=self.storage_manager,
            config=config
        )
        
        # 开始处理
        return await pipeline.process_document(
            file_path=file_path,
            document_id=document_id,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            filename=os.path.basename(file_path),
            content_type=mimetypes.guess_type(file_path)[0]
        )
        
    async def get_processing_status(self, document_id: str) -> Dict[str, Any]:
        """获取处理状态"""
        # 实现状态查询逻辑
        pass
```

### 8.2 V1 API路由集成

```python
# server/app/v1/routers/documents.py
from server.core.service import DocumentProcessingService

@router.post("/knowledge-bases/{kb_id}/documents")
async def process_document_to_knowledge_base(
    kb_id: str,
    request: ProcessDocumentRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: DocumentProcessingService = Depends(get_document_service)
):
    """处理文档到知识库 - 集成Core层"""
    
    try:
        # 获取文件信息
        file_info = await get_file_info(request.file_id, current_user.user_id, db)
        
        # 启动处理
        result = await service.start_document_processing(
            file_path=file_info.local_path,  # 假设本地路径存在
            document_id=generate_document_id(),
            user_id=current_user.user_id,
            knowledge_base_id=kb_id,
            mode=ProcessingMode(request.mode)
        )
        
        if result.success:
            return StandardResponse(
                success=True,
                message="Document processing started successfully",
                document=result.context.to_api_response()
            )
        else:
            raise HTTPException(status_code=500, detail=result.message)
            
    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**验证**:
- [ ] API路由正确集成
- [ ] 请求参数验证
- [ ] 响应格式正确
- [ ] 错误处理完善
- [ ] 认证授权集成

## 9. 测试套件

### 9.1 单元测试

创建测试文件结构:
```
tests/core/
├── test_models/
├── test_processors/
├── test_strategies/
├── test_pipeline/
└── test_storage/
```

**测试内容**:
- [ ] 数据模型测试
- [ ] 处理器单元测试
- [ ] 策略算法测试
- [ ] Pipeline流程测试
- [ ] 存储接口测试

### 9.2 集成测试

```python
# tests/integration/test_document_processing.py
import pytest
from server.core.service import DocumentProcessingService

@pytest.mark.asyncio
async def test_complete_document_processing():
    """完整文档处理集成测试"""
    # 准备测试数据
    test_file = "tests/data/sample.pdf"
    
    # 创建服务
    service = DocumentProcessingService(db_session, storage_manager, config_manager)
    
    # 执行处理
    result = await service.start_document_processing(
        file_path=test_file,
        document_id="test_doc_001",
        user_id="test_user",
        knowledge_base_id="test_kb",
        mode=ProcessingMode.NORMAL
    )
    
    # 验证结果
    assert result.success
    assert result.context.total_chunks > 0
    assert len(result.context.embeddings) > 0
```

**验证**:
- [ ] 完整流程集成测试
- [ ] 错误场景测试
- [ ] 性能测试
- [ ] 并发测试
- [ ] 资源清理测试

## 10. 部署和监控

### 10.1 配置管理

```python
# server/core/config.py
from pydantic import BaseSettings

class CoreSettings(BaseSettings):
    # MinIO配置
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    
    # OpenAI配置
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-ada-002"
    
    # PostgreSQL配置
    database_url: str
    
    # 处理配置
    max_concurrent_processing: int = 5
    default_processing_timeout: int = 3600
    
    class Config:
        env_file = ".env"
```

### 10.2 日志和监控

```python
# server/core/monitoring.py
import logging
from prometheus_client import Counter, Histogram, Gauge

# 性能指标
processing_duration = Histogram('document_processing_duration_seconds', 'Document processing duration', ['stage', 'mode'])
processing_counter = Counter('document_processing_total', 'Total processed documents', ['status', 'mode'])
active_processing = Gauge('document_processing_active', 'Currently active processing tasks')

class ProcessingMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def record_processing_start(self, document_id: str, mode: str):
        """记录处理开始"""
        active_processing.inc()
        self.logger.info(f"Started processing document {document_id} in {mode} mode")
        
    def record_processing_complete(self, document_id: str, mode: str, duration: float):
        """记录处理完成"""
        active_processing.dec()
        processing_counter.labels(status='success', mode=mode).inc()
        processing_duration.labels(stage='total', mode=mode).observe(duration)
        self.logger.info(f"Completed processing document {document_id} in {duration:.2f}s")
```

**验证**:
- [ ] 配置加载测试
- [ ] 日志输出验证
- [ ] 监控指标收集
- [ ] 告警规则设置

## 完成检查

### 最终验证清单

- [ ] **功能完整性**: 所有设计的功能都已实现
- [ ] **API兼容性**: 与API_REFERENCE.md中的接口完全兼容  
- [ ] **错误处理**: 各种异常场景都有适当处理
- [ ] **性能要求**: 满足处理速度和并发要求
- [ ] **资源管理**: 内存和文件资源得到正确管理
- [ ] **监控覆盖**: 关键指标都有监控
- [ ] **文档更新**: 所有文档都已更新
- [ ] **测试覆盖**: 测试覆盖率达到要求

### 部署前检查

- [ ] **环境配置**: 所有环境变量配置正确
- [ ] **依赖安装**: 所有依赖包正确安装
- [ ] **数据库迁移**: 数据库表结构正确创建
- [ ] **存储连接**: MinIO和向量数据库连接正常
- [ ] **API测试**: 所有API接口测试通过
- [ ] **负载测试**: 系统能处理预期负载
- [ ] **监控启用**: 监控系统正常工作

完成这个清单后，Core层就可以成功集成到V1 API中，提供完整的文档处理能力。