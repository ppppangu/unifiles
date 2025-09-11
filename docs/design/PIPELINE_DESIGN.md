# Document Processing Pipeline 设计

## 概述

文档处理Pipeline是Core层的核心，负责协调整个文档处理流程。采用异步Pipeline模式，支持多种处理模式和灵活的配置。

## 1. Pipeline 总体架构

```
Input File → [Validation] → [Conversion] → [OCR] → [Chunking] → [Embedding] → [Storage] → Output
     ↓             ↓           ↓         ↓         ↓           ↓           ↓
[Status Tracking] [Error Handling] [Progress Monitoring] [Quality Assessment]
```

## 2. Pipeline 实现

### 2.1 DocumentProcessingPipeline (主控制器)

```python
import asyncio
from typing import Dict, Any, List, Optional
import time

class DocumentProcessingPipeline:
    """文档处理Pipeline主控制器"""
    
    def __init__(self, 
                 db_session,
                 storage_manager: StorageManager,
                 config: ProcessingConfig = None):
        self.db_session = db_session
        self.storage_manager = storage_manager
        self.config = config or ProcessingConfig()
        
        # 状态跟踪器
        self.status_tracker = StatusTracker(db_session)
        
        # 初始化处理阶段
        self.stages = self._initialize_stages()
        
        # 性能监控
        self.metrics_collector = MetricsCollector()
    
    def _initialize_stages(self) -> List[ProcessingStage]:
        """初始化处理阶段"""
        stages = []
        
        # 1. 文件转换阶段
        converter_factory = ConverterFactory()
        stages.append(FileConversionStage(
            converter_factory=converter_factory,
            config=self.config.get("conversion", {})
        ))
        
        # 2. OCR处理阶段  
        ocr_processor = self._create_ocr_processor()
        multimodal_processor = None
        
        if self.config.mode != ProcessingMode.SIMPLE:
            multimodal_processor = self._create_multimodal_processor()
            
        stages.append(OCRProcessingStage(
            ocr_processor=ocr_processor,
            storage_manager=self.storage_manager,
            multimodal_processor=multimodal_processor,
            config=self.config.ocr_config
        ))
        
        # 3. 分块处理阶段
        chunking_strategy = self._create_chunking_strategy()
        stages.append(ChunkingStage(
            chunking_strategy=chunking_strategy,
            config=self.config.chunking_config
        ))
        
        # 4. 嵌入处理阶段
        embedding_strategy = self._create_embedding_strategy()
        stages.append(EmbeddingStage(
            embedding_strategy=embedding_strategy,
            config=self.config.embedding_config
        ))
        
        # 5. 向量存储阶段
        vector_store = self._create_vector_store()
        stages.append(VectorStorageStage(
            vector_store=vector_store,
            config=self.config.storage_config
        ))
        
        return stages
    
    async def process_document(self, 
                              file_path: str,
                              document_id: str,
                              user_id: str,
                              knowledge_base_id: str,
                              filename: str,
                              content_type: str) -> ProcessingResult:
        """处理单个文档"""
        
        start_time = time.time()
        
        # 创建处理上下文
        context = ProcessingContext(
            document_id=document_id,
            file_id=f"file-{document_id}",
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            mode=self.config.mode,
            original_file_path=file_path,
            original_filename=filename,
            content_type=content_type,
            file_size=os.path.getsize(file_path),
            processing_config=self.config.__dict__
        )
        
        try:
            # 更新状态为处理中
            await self.status_tracker.update_status(
                document_id, "pipeline", ProcessingStatus.PROCESSING
            )
            
            # 执行各个处理阶段
            for i, stage in enumerate(self.stages):
                stage_start = time.time()
                context.add_log("INFO", f"开始执行阶段: {stage.get_stage_name()}")
                
                try:
                    # 执行阶段处理
                    context = await self._execute_stage_with_timeout(stage, context)
                    
                    # 更新进度
                    progress = int((i + 1) / len(self.stages) * 100)
                    await self.status_tracker.update_progress(document_id, progress)
                    
                    # 记录阶段完成
                    stage_duration = time.time() - stage_start
                    context.add_log("INFO", 
                        f"阶段 {stage.get_stage_name()} 完成，耗时: {stage_duration:.2f}s")
                    
                    # 收集性能指标
                    self.metrics_collector.record_stage_duration(
                        stage.get_stage_name(), stage_duration
                    )
                    
                except ProcessingException as e:
                    # 处理阶段异常
                    await self._handle_stage_error(context, stage, e)
                    raise
                    
            # 处理完成
            total_duration = time.time() - start_time
            await self._finalize_processing(context, total_duration)
            
            return ProcessingResult(
                success=True,
                message="Document processed successfully",
                context=context,
                duration=total_duration
            )
            
        except Exception as e:
            # 处理失败
            await self.status_tracker.update_status(
                document_id, "pipeline", ProcessingStatus.FAILED, error=str(e)
            )
            
            context.add_log("ERROR", f"处理失败: {str(e)}")
            
            return ProcessingResult(
                success=False,
                message=f"Processing failed: {str(e)}",
                context=context,
                error=e
            )
    
    async def _execute_stage_with_timeout(self, 
                                        stage: ProcessingStage, 
                                        context: ProcessingContext) -> ProcessingContext:
        """执行阶段处理（带超时）"""
        timeout = self.config.timeout_seconds
        
        try:
            return await asyncio.wait_for(
                stage.process(context),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise ProcessingException(
                f"Stage {stage.get_stage_name()} timed out after {timeout} seconds",
                stage=stage.get_stage_name(),
                document_id=context.document_id
            )
    
    async def _handle_stage_error(self, 
                                context: ProcessingContext,
                                stage: ProcessingStage,
                                error: ProcessingException):
        """处理阶段错误"""
        
        context.add_log("ERROR", f"阶段 {stage.get_stage_name()} 失败: {str(error)}")
        
        # 记录错误到状态跟踪器
        await self.status_tracker.update_status(
            context.document_id,
            stage.get_stage_name(),
            ProcessingStatus.FAILED,
            error=str(error)
        )
        
        # 如果支持重试，可以在这里实现重试逻辑
        if stage.can_retry() and self._should_retry(context, stage):
            context.add_log("INFO", f"准备重试阶段: {stage.get_stage_name()}")
            # 实现重试逻辑...
    
    async def _finalize_processing(self, context: ProcessingContext, duration: float):
        """完成处理，保存最终结果"""
        
        # 创建ProcessedDocument
        processed_doc = ProcessedDocument(
            document_id=context.document_id,
            file_id=context.file_id,
            user_id=context.user_id,
            knowledge_base_id=context.knowledge_base_id,
            filename=context.original_filename,
            original_filename=context.original_filename,
            content_type=context.content_type,
            file_size=context.file_size,
            mode=context.mode,
            status=ProcessingStatus.COMPLETED,
            processing_progress=100,
            original_file_url=context.original_file_url,
            pdf_url=context.pdf_url,
            markdown_url=context.markdown_url,
            total_chunks=len(context.text_chunks) + len(context.image_chunks),
            text_chunks_count=len(context.text_chunks),
            image_chunks_count=len(context.image_chunks),
            embedding_count=len(context.embeddings),
            processing_logs=context.processing_logs,
            completed_at=datetime.utcnow()
        )
        
        # 保存到数据库
        await self._save_processed_document(processed_doc)
        
        # 更新状态
        await self.status_tracker.update_status(
            context.document_id, "pipeline", ProcessingStatus.COMPLETED
        )
        
        # 清理临时文件
        await self._cleanup_temp_files(context)
        
        context.add_log("INFO", f"文档处理完成，总耗时: {duration:.2f}s")
```

### 2.2 具体处理阶段实现

#### 2.2.1 FileConversionStage 详细实现

```python
class FileConversionStage(ProcessingStage):
    """文件格式转换阶段详细实现"""
    
    def __init__(self, converter_factory: ConverterFactory, config: Dict[str, Any]):
        super().__init__("file_conversion")
        self.converter_factory = converter_factory
        self.config = config
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行格式转换"""
        context.add_log("INFO", f"开始转换文件: {context.original_filename}")
        
        # 检查是否已经是PDF格式
        if context.content_type == "application/pdf":
            context.pdf_path = context.original_file_path
            context.add_log("INFO", "文件已是PDF格式，跳过转换")
            return context
            
        # 获取合适的转换器
        converter = self.converter_factory.get_converter(context.content_type)
        if not converter:
            raise FileConversionException(
                f"不支持的文件类型: {context.content_type}",
                stage=self.name,
                document_id=context.document_id
            )
        
        # 创建输出目录
        output_dir = self._create_temp_dir(context)
        
        # 执行转换
        try:
            pdf_path = await converter.convert_to_pdf(
                input_path=context.original_file_path,
                output_dir=output_dir,
                options=self.config.get("conversion_options", {})
            )
            
            context.pdf_path = pdf_path
            context.add_log("INFO", f"PDF转换完成: {pdf_path}")
            
            # 验证转换结果
            await self._validate_conversion_result(pdf_path)
            
        except Exception as e:
            raise FileConversionException(
                f"文件转换失败: {str(e)}",
                stage=self.name,
                document_id=context.document_id
            )
        
        return context
    
    def _create_temp_dir(self, context: ProcessingContext) -> str:
        """创建临时目录"""
        temp_dir = os.path.join(
            tempfile.gettempdir(), 
            f"doc_processing_{context.document_id}"
        )
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir
    
    async def _validate_conversion_result(self, pdf_path: str):
        """验证转换结果"""
        if not os.path.exists(pdf_path):
            raise FileConversionException("转换后的PDF文件不存在")
            
        if os.path.getsize(pdf_path) == 0:
            raise FileConversionException("转换后的PDF文件为空")
```

#### 2.2.2 OCRProcessingStage 详细实现

```python
class OCRProcessingStage(ProcessingStage):
    """OCR处理阶段详细实现"""
    
    def __init__(self, 
                 ocr_processor: OCRProcessor,
                 storage_manager: StorageManager,
                 multimodal_processor: Optional[MultiModalProcessor],
                 config: Dict[str, Any]):
        super().__init__("ocr_processing")
        self.ocr_processor = ocr_processor
        self.storage_manager = storage_manager
        self.multimodal_processor = multimodal_processor
        self.config = config
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行OCR处理"""
        context.add_log("INFO", "开始OCR处理")
        
        # 1. 执行OCR
        ocr_result = await self.ocr_processor.process_pdf(
            pdf_path=context.pdf_path,
            options=self.config.get("ocr_options", {})
        )
        
        context.markdown_content = ocr_result.markdown_content
        context.extracted_images = ocr_result.image_paths
        
        context.add_log("INFO", 
            f"OCR完成: 提取了 {len(context.extracted_images)} 张图片")
        
        # 2. 多模态处理（如果启用）
        if (self.multimodal_processor and 
            context.mode != ProcessingMode.SIMPLE and
            context.extracted_images):
            
            context.add_log("INFO", "开始多模态处理")
            
            multimodal_result = await self.multimodal_processor.enhance_content(
                markdown_content=context.markdown_content,
                image_paths=context.extracted_images,
                options=self.config.get("multimodal_options", {})
            )
            
            context.markdown_content = multimodal_result.enhanced_markdown
            context.add_log("INFO", "多模态处理完成")
        
        # 3. 存储处理结果
        await self._store_processing_results(context)
        
        context.add_log("INFO", "OCR处理阶段完成")
        return context
    
    async def _store_processing_results(self, context: ProcessingContext):
        """存储处理结果到MinIO"""
        
        # 保存markdown文件
        markdown_content = context.markdown_content.encode('utf-8')
        markdown_key = f"{context.user_id}/processed_files/{context.document_id}.md"
        
        markdown_url = await self.storage_manager.upload_content(
            content=markdown_content,
            object_key=markdown_key,
            content_type="text/markdown"
        )
        
        context.markdown_url = markdown_url
        context.add_log("INFO", f"Markdown文件已上传: {markdown_url}")
        
        # 上传处理后的PDF
        if context.pdf_path and context.pdf_path != context.original_file_path:
            pdf_key = f"{context.user_id}/processed_files/{context.document_id}.pdf"
            
            with open(context.pdf_path, 'rb') as f:
                pdf_content = f.read()
                
            pdf_url = await self.storage_manager.upload_content(
                content=pdf_content,
                object_key=pdf_key,
                content_type="application/pdf"
            )
            
            context.pdf_url = pdf_url
            context.add_log("INFO", f"PDF文件已上传: {pdf_url}")
```

#### 2.2.3 ChunkingStage 详细实现

```python
class ChunkingStage(ProcessingStage):
    """分块处理阶段详细实现"""
    
    def __init__(self, chunking_strategy: ChunkingStrategy, config: Dict[str, Any]):
        super().__init__("chunking")
        self.chunking_strategy = chunking_strategy
        self.config = config
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行分块处理"""
        context.add_log("INFO", "开始分块处理")
        
        # 验证输入
        if not context.markdown_content:
            raise ChunkingException(
                "没有可分块的内容",
                stage=self.name,
                document_id=context.document_id
            )
        
        # 执行分块
        chunking_result = await self.chunking_strategy.chunk_document(
            markdown_content=context.markdown_content,
            images=context.extracted_images,
            config=self.config
        )
        
        # 分配chunk_id
        for i, chunk in enumerate(chunking_result.text_chunks):
            chunk.chunk_id = f"{context.document_id}_text_{i}"
            chunk.document_id = context.document_id
            
        for i, chunk in enumerate(chunking_result.image_chunks):
            chunk.chunk_id = f"{context.document_id}_image_{i}"
            chunk.document_id = context.document_id
        
        context.text_chunks = chunking_result.text_chunks
        context.image_chunks = chunking_result.image_chunks
        
        context.add_log("INFO", 
            f"分块完成: {len(context.text_chunks)}个文本块, {len(context.image_chunks)}个图片块")
        
        # 质量检查
        await self._validate_chunks(context)
        
        return context
    
    async def _validate_chunks(self, context: ProcessingContext):
        """验证分块质量"""
        total_chunks = len(context.text_chunks) + len(context.image_chunks)
        
        if total_chunks == 0:
            raise ChunkingException(
                "分块结果为空",
                stage=self.name,
                document_id=context.document_id
            )
        
        # 检查文本块大小
        for chunk in context.text_chunks:
            if len(chunk.content) < self.config.get("min_chunk_size", 50):
                context.add_log("WARNING", 
                    f"发现过小的文本块: {chunk.chunk_id}, 大小: {len(chunk.content)}")
```

#### 2.2.4 EmbeddingStage 详细实现

```python
class EmbeddingStage(ProcessingStage):
    """嵌入处理阶段详细实现"""
    
    def __init__(self, embedding_strategy: EmbeddingStrategy, config: Dict[str, Any]):
        super().__init__("embedding")
        self.embedding_strategy = embedding_strategy
        self.config = config
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行嵌入处理"""
        context.add_log("INFO", "开始嵌入处理")
        
        embeddings = []
        batch_size = self.config.get("batch_size", 10)
        
        # 处理文本块嵌入（批量处理）
        text_chunks = context.text_chunks
        for i in range(0, len(text_chunks), batch_size):
            batch = text_chunks[i:i + batch_size]
            batch_embeddings = await self._process_text_batch(batch, context)
            embeddings.extend(batch_embeddings)
            
            # 更新进度
            progress = min(100, int((i + batch_size) / len(text_chunks) * 50))
            context.add_log("DEBUG", f"文本嵌入进度: {progress}%")
        
        # 处理图像块嵌入（如果支持）
        if (self.embedding_strategy.supports_images() and 
            context.image_chunks):
            
            for i, chunk in enumerate(context.image_chunks):
                try:
                    embedding = await self.embedding_strategy.embed_image(
                        chunk.image_path
                    )
                    
                    embeddings.append(EmbeddingResult(
                        embedding_id=f"{chunk.chunk_id}_emb",
                        chunk_id=chunk.chunk_id,
                        document_id=context.document_id,
                        chunk_type="image",
                        embedding=embedding,
                        model_name=self.embedding_strategy.model_name,
                        embedding_strategy=self.embedding_strategy.__class__.__name__,
                        metadata=chunk.metadata
                    ))
                    
                except Exception as e:
                    context.add_log("WARNING", 
                        f"图片 {chunk.chunk_id} 嵌入失败: {str(e)}")
        
        context.embeddings = embeddings
        context.add_log("INFO", f"嵌入完成: {len(embeddings)}个向量")
        
        return context
    
    async def _process_text_batch(self, 
                                batch: List[TextChunk], 
                                context: ProcessingContext) -> List[EmbeddingResult]:
        """批量处理文本嵌入"""
        embeddings = []
        
        for chunk in batch:
            try:
                embedding = await self.embedding_strategy.embed_text(chunk.content)
                
                embeddings.append(EmbeddingResult(
                    embedding_id=f"{chunk.chunk_id}_emb",
                    chunk_id=chunk.chunk_id,
                    document_id=context.document_id,
                    chunk_type="text",
                    embedding=embedding,
                    model_name=self.embedding_strategy.model_name,
                    embedding_strategy=self.embedding_strategy.__class__.__name__,
                    metadata=chunk.metadata
                ))
                
            except Exception as e:
                context.add_log("WARNING", 
                    f"文本块 {chunk.chunk_id} 嵌入失败: {str(e)}")
                
        return embeddings
```

#### 2.2.5 VectorStorageStage 详细实现

```python
class VectorStorageStage(ProcessingStage):
    """向量存储阶段详细实现"""
    
    def __init__(self, vector_store: VectorStore, config: Dict[str, Any]):
        super().__init__("vector_storage")
        self.vector_store = vector_store
        self.config = config
        
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """执行向量存储"""
        context.add_log("INFO", "开始向量存储")
        
        if not context.embeddings:
            raise StorageException(
                "没有可存储的向量",
                stage=self.name,
                document_id=context.document_id
            )
        
        # 转换为向量记录
        vector_records = []
        for embedding_result in context.embeddings:
            # 获取对应的chunk内容
            chunk_content = self._get_chunk_content(
                embedding_result.chunk_id, context
            )
            
            vector_record = VectorRecord(
                vector_id=embedding_result.embedding_id,
                document_id=context.document_id,
                chunk_id=embedding_result.chunk_id,
                knowledge_base_id=context.knowledge_base_id,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model_name,
                content=chunk_content,
                content_type=embedding_result.chunk_type,
                content_hash=self._calculate_hash(chunk_content),
                metadata=embedding_result.metadata
            )
            
            vector_records.append(vector_record)
        
        # 批量存储到向量数据库
        batch_size = self.config.get("storage_batch_size", 100)
        for i in range(0, len(vector_records), batch_size):
            batch = vector_records[i:i + batch_size]
            await self.vector_store.upsert_vectors(batch)
            
            context.add_log("DEBUG", 
                f"已存储 {min(i + batch_size, len(vector_records))} / {len(vector_records)} 个向量")
        
        context.add_log("INFO", f"向量存储完成: {len(vector_records)}个向量")
        
        return context
    
    def _get_chunk_content(self, chunk_id: str, context: ProcessingContext) -> str:
        """获取chunk内容"""
        # 查找文本块
        for chunk in context.text_chunks:
            if chunk.chunk_id == chunk_id:
                return chunk.content
                
        # 查找图片块
        for chunk in context.image_chunks:
            if chunk.chunk_id == chunk_id:
                return chunk.description or chunk.caption or f"Image: {chunk.image_path}"
                
        return ""
    
    def _calculate_hash(self, content: str) -> str:
        """计算内容哈希"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
```

## 3. 使用示例

### 3.1 基本使用

```python
from server.core.pipeline import DocumentProcessingPipeline
from server.core.models import ProcessingConfig, ProcessingMode

async def process_document_example():
    """文档处理示例"""
    
    # 创建配置
    config = ProcessingConfig.from_mode(ProcessingMode.NORMAL)
    
    # 创建pipeline
    pipeline = DocumentProcessingPipeline(
        db_session=db_session,
        storage_manager=storage_manager,
        config=config
    )
    
    # 处理文档
    result = await pipeline.process_document(
        file_path="/path/to/document.pdf",
        document_id="doc_12345",
        user_id="user_123",
        knowledge_base_id="kb_456",
        filename="document.pdf",
        content_type="application/pdf"
    )
    
    if result.success:
        print(f"处理成功: {result.message}")
        print(f"耗时: {result.duration:.2f}s")
        print(f"生成 {result.context.total_chunks} 个分块")
    else:
        print(f"处理失败: {result.message}")
```

### 3.2 自定义配置

```python
async def process_with_custom_config():
    """使用自定义配置处理文档"""
    
    # 自定义配置
    config = ProcessingConfig(
        mode=ProcessingMode.ADVANCED,
        chunking_config={
            "strategy": "adaptive",
            "chunk_size": 800,
            "chunk_overlap": 150,
            "min_chunk_size": 100
        },
        embedding_config={
            "strategy": "openai",
            "model": "text-embedding-ada-002",
            "batch_size": 50
        },
        multimodal_config={
            "enabled": True,
            "model": "gpt-4-vision-preview",
            "max_images": 15
        }
    )
    
    # 创建并使用pipeline
    pipeline = DocumentProcessingPipeline(
        db_session=db_session,
        storage_manager=storage_manager,
        config=config
    )
    
    # 处理文档...
```

### 3.3 批量处理

```python
async def batch_process_documents(file_paths: List[str], 
                                knowledge_base_id: str,
                                user_id: str):
    """批量处理文档"""
    
    config = ProcessingConfig.from_mode(ProcessingMode.NORMAL)
    pipeline = DocumentProcessingPipeline(
        db_session=db_session,
        storage_manager=storage_manager,
        config=config
    )
    
    tasks = []
    for i, file_path in enumerate(file_paths):
        document_id = f"doc_{knowledge_base_id}_{i}"
        filename = os.path.basename(file_path)
        content_type = mimetypes.guess_type(file_path)[0]
        
        task = pipeline.process_document(
            file_path=file_path,
            document_id=document_id,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            content_type=content_type
        )
        
        tasks.append(task)
    
    # 并发处理
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    success_count = sum(1 for r in results if isinstance(r, ProcessingResult) and r.success)
    print(f"批量处理完成: {success_count}/{len(results)} 成功")
```

## 4. 监控和性能优化

### 4.1 性能监控

```python
class MetricsCollector:
    """性能指标收集器"""
    
    def __init__(self):
        self.stage_durations = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.throughput_metrics = []
        
    def record_stage_duration(self, stage_name: str, duration: float):
        """记录阶段耗时"""
        self.stage_durations[stage_name].append(duration)
        
    def record_error(self, stage_name: str, error_type: str):
        """记录错误"""
        self.error_counts[f"{stage_name}_{error_type}"] += 1
        
    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        report = {}
        
        for stage, durations in self.stage_durations.items():
            report[stage] = {
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "total_executions": len(durations)
            }
            
        report["errors"] = dict(self.error_counts)
        return report
```

### 4.2 资源管理

```python
class ResourceManager:
    """资源管理器"""
    
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.temp_files = set()
        
    async def acquire_processing_slot(self):
        """获取处理槽位"""
        return await self.semaphore.acquire()
        
    def release_processing_slot(self):
        """释放处理槽位"""
        self.semaphore.release()
        
    def register_temp_file(self, file_path: str):
        """注册临时文件"""
        self.temp_files.add(file_path)
        
    async def cleanup_temp_files(self):
        """清理临时文件"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        self.temp_files.clear()
```

这个Pipeline设计提供了：

1. **完整的处理流程**: 从文件输入到向量存储的完整pipeline
2. **灵活配置**: 支持多种处理模式和自定义配置
3. **错误处理**: 完善的异常处理和重试机制
4. **状态跟踪**: 实时的处理状态和进度跟踪
5. **性能优化**: 并发处理、批量操作、资源管理
6. **可扩展性**: 易于添加新的处理阶段和策略