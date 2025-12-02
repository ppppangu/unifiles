# 处理管线

本文档详细介绍 Unifiles 的文档处理管线，从文件上传到知识库索引的完整流程。

## 管线概览

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  上传   │ →  │  验证   │ →  │  转换   │ →  │  OCR   │ →  │ 后处理  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                                                 │
                                                                 ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  搜索   │ ←  │  索引   │ ←  │  嵌入   │ ←  │  分块   │ ←  │ Markdown│
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

## 阶段详解

### Stage 1: 文件上传

```python
# 上传流程
async def upload_file(file: UploadFile, user_id: str) -> File:
    # 1. 生成文件 ID
    file_id = generate_uuid()
    
    # 2. 计算内容哈希 (用于去重)
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    
    # 3. 检查是否已存在相同文件
    existing = await find_file_by_hash(user_id, content_hash)
    if existing:
        return existing  # 直接返回已有文件
    
    # 4. 存储到 MinIO
    storage_key = f"raw/{user_id}/{file_id}/{file.filename}"
    await storage.upload(
        bucket="unifiles-raw",
        key=storage_key,
        data=content
    )
    
    # 5. 保存元数据到 PostgreSQL
    file_record = await save_file_record(
        id=file_id,
        user_id=user_id,
        filename=file.filename,
        storage_key=storage_key,
        content_hash=content_hash,
        size=len(content),
        status="uploaded"
    )
    
    return file_record
```

### Stage 2: 文件验证

验证阶段检查文件的合法性：

```python
class FileValidator:
    ALLOWED_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/html": ".html",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }
    
    async def validate(self, file: UploadFile) -> ValidationResult:
        errors = []
        
        # 1. 检查 MIME 类型
        if file.content_type not in self.ALLOWED_TYPES:
            errors.append(f"Unsupported file type: {file.content_type}")
        
        # 2. 检查文件大小
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            errors.append(f"File too large: {len(content)} bytes")
        
        # 3. 检查文件内容 (magic bytes)
        detected_type = magic.from_buffer(content, mime=True)
        if detected_type != file.content_type:
            errors.append(f"Content type mismatch: declared {file.content_type}, detected {detected_type}")
        
        # 4. 检查文件是否损坏
        if not await self.is_valid_file(content, file.content_type):
            errors.append("File appears to be corrupted")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
```

### Stage 3: 格式转换

将各种格式统一转换为可处理的中间格式：

```python
class FormatConverter:
    """格式转换器"""
    
    async def convert(self, file_path: str, mime_type: str) -> ConversionResult:
        if mime_type == "application/pdf":
            return await self.process_pdf(file_path)
        elif mime_type.startswith("application/vnd.openxmlformats"):
            return await self.process_office(file_path)
        elif mime_type.startswith("image/"):
            return await self.process_image(file_path)
        elif mime_type.startswith("text/"):
            return await self.process_text(file_path)
        else:
            raise UnsupportedFormatError(mime_type)
    
    async def process_pdf(self, file_path: str) -> ConversionResult:
        """处理 PDF 文件"""
        pages = []
        
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                # 提取文本
                text = page.get_text("text")
                
                # 提取表格
                tables = page.find_tables()
                
                # 如果文本很少，可能是扫描件，需要 OCR
                if len(text.strip()) < 100:
                    # 渲染为图片
                    pix = page.get_pixmap(dpi=300)
                    image_path = f"/tmp/page_{page_num}.png"
                    pix.save(image_path)
                    pages.append(PageResult(
                        page_num=page_num,
                        text=text,
                        tables=tables,
                        needs_ocr=True,
                        image_path=image_path
                    ))
                else:
                    pages.append(PageResult(
                        page_num=page_num,
                        text=text,
                        tables=tables,
                        needs_ocr=False
                    ))
        
        return ConversionResult(pages=pages)
```

### Stage 4: OCR 识别

对需要 OCR 的页面进行文字识别：

```python
class OCRProcessor:
    """OCR 处理器"""
    
    def __init__(self, provider: str = "internal"):
        self.provider = self._create_provider(provider)
    
    async def process(self, pages: list[PageResult]) -> list[PageResult]:
        """处理需要 OCR 的页面"""
        
        tasks = []
        for page in pages:
            if page.needs_ocr:
                tasks.append(self._ocr_page(page))
            else:
                tasks.append(asyncio.sleep(0, result=page))
        
        return await asyncio.gather(*tasks)
    
    async def _ocr_page(self, page: PageResult) -> PageResult:
        """对单页进行 OCR"""
        
        # 调用 OCR 提供商
        result = await self.provider.recognize(page.image_path)
        
        # 合并 OCR 结果
        page.text = result.text
        page.ocr_confidence = result.confidence
        page.ocr_boxes = result.boxes  # 文字位置信息
        
        return page
```

支持的 OCR 提供商：

| 提供商 | 特点 |
|-------|------|
| 内置 (Tesseract) | 免费，离线，基础准确率 |
| 阿里云 OCR | 高精度，支持中文 |
| Azure Document Intelligence | 结构化提取 |
| 自定义 | 通过接口扩展 |

### Stage 5: 后处理

将 OCR 结果转换为结构化 Markdown：

```python
class PostProcessor:
    """后处理器：生成 Markdown"""
    
    async def process(self, pages: list[PageResult]) -> MarkdownResult:
        markdown_parts = []
        
        for page in pages:
            # 1. 处理标题
            headings = self._extract_headings(page)
            
            # 2. 处理段落
            paragraphs = self._extract_paragraphs(page)
            
            # 3. 处理表格
            tables = self._format_tables(page.tables)
            
            # 4. 处理图片引用
            images = self._extract_images(page)
            
            # 5. 组装 Markdown
            page_md = self._assemble_markdown(
                headings, paragraphs, tables, images
            )
            markdown_parts.append(page_md)
        
        # 合并所有页面
        full_markdown = "\n\n".join(markdown_parts)
        
        # 提取元数据
        metadata = self._extract_metadata(pages)
        
        return MarkdownResult(
            content=full_markdown,
            metadata=metadata,
            page_count=len(pages),
            word_count=len(full_markdown.split())
        )
    
    def _format_tables(self, tables: list) -> str:
        """将表格转换为 Markdown 格式"""
        result = []
        
        for table in tables:
            # 表头
            header = "| " + " | ".join(table[0]) + " |"
            separator = "| " + " | ".join(["---"] * len(table[0])) + " |"
            
            # 表体
            body = []
            for row in table[1:]:
                body.append("| " + " | ".join(row) + " |")
            
            result.append("\n".join([header, separator] + body))
        
        return "\n\n".join(result)
```

### Stage 6: 文本分块

将 Markdown 内容分割为适合检索的块：

```python
class TextChunker:
    """文本分块器"""
    
    def __init__(
        self,
        strategy: str = "semantic",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk(self, text: str) -> list[Chunk]:
        if self.strategy == "fixed":
            return self._fixed_chunk(text)
        elif self.strategy == "semantic":
            return self._semantic_chunk(text)
        elif self.strategy == "paragraph":
            return self._paragraph_chunk(text)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _semantic_chunk(self, text: str) -> list[Chunk]:
        """语义分块：在语义边界处分割"""
        chunks = []
        
        # 首先按段落分割
        paragraphs = text.split("\n\n")
        
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_tokens = self._count_tokens(para)
            
            if current_size + para_tokens > self.chunk_size:
                # 保存当前块
                if current_chunk:
                    chunks.append(Chunk(
                        content="\n\n".join(current_chunk),
                        token_count=current_size
                    ))
                
                # 开始新块 (包含重叠)
                overlap_paras = self._get_overlap(current_chunk)
                current_chunk = overlap_paras + [para]
                current_size = sum(self._count_tokens(p) for p in current_chunk)
            else:
                current_chunk.append(para)
                current_size += para_tokens
        
        # 保存最后一块
        if current_chunk:
            chunks.append(Chunk(
                content="\n\n".join(current_chunk),
                token_count=current_size
            ))
        
        return chunks
```

### Stage 7: 向量嵌入

为每个分块生成向量嵌入：

```python
class EmbeddingService:
    """嵌入服务"""
    
    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small"
    ):
        self.provider = provider
        self.model = model
        self.client = self._create_client()
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入"""
        
        # 分批处理 (OpenAI 限制)
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=batch
            )
            
            embeddings = [e.embedding for e in response.data]
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def embed_single(self, text: str) -> list[float]:
        """生成单个嵌入"""
        embeddings = await self.embed([text])
        return embeddings[0]
```

### Stage 8: 向量索引

将分块和嵌入存储到 pgvector：

```python
class VectorIndexer:
    """向量索引器"""
    
    async def index(
        self,
        document_id: str,
        kb_id: str,
        chunks: list[Chunk],
        embeddings: list[list[float]]
    ):
        """索引文档分块"""
        
        async with self.pool.acquire() as conn:
            # 批量插入
            await conn.executemany(
                """
                INSERT INTO chunks (
                    id, document_id, knowledge_base_id,
                    content, token_count, chunk_index,
                    embedding, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        document_id,
                        kb_id,
                        chunk.content,
                        chunk.token_count,
                        i,
                        embedding,
                        json.dumps(chunk.metadata or {})
                    )
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
                ]
            )
            
            # 更新文档统计
            await conn.execute(
                """
                UPDATE documents 
                SET chunk_count = $1, status = 'indexed', indexed_at = NOW()
                WHERE id = $2
                """,
                len(chunks),
                document_id
            )
```

### Stage 9: 向量搜索

执行语义相似度搜索：

```python
class VectorSearch:
    """向量搜索"""
    
    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
        filters: dict = None
    ) -> list[SearchResult]:
        """执行向量搜索"""
        
        # 1. 生成查询向量
        query_embedding = await self.embedding_service.embed_single(query)
        
        # 2. 构建查询
        sql = """
            SELECT 
                c.id,
                c.content,
                c.metadata,
                c.document_id,
                d.title as document_title,
                1 - (c.embedding <=> $1::vector) as similarity
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.knowledge_base_id = $2
        """
        params = [query_embedding, kb_id]
        
        # 3. 应用过滤器
        if filters:
            if "metadata" in filters:
                sql += " AND c.metadata @> $3"
                params.append(json.dumps(filters["metadata"]))
        
        # 4. 排序和限制
        sql += " ORDER BY c.embedding <=> $1::vector LIMIT $" + str(len(params) + 1)
        params.append(top_k)
        
        # 5. 执行查询
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        
        # 6. 构建结果
        results = [
            SearchResult(
                chunk_id=row["id"],
                content=row["content"],
                score=row["similarity"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                metadata=json.loads(row["metadata"])
            )
            for row in rows
        ]
        
        return results
```

## 处理状态机

```
           ┌──────────────────────────────────────────┐
           │                                          │
           ▼                                          │
     ┌──────────┐                                     │
     │ uploaded │ ──────────────────────┐             │
     └────┬─────┘                       │             │
          │                             │             │
          ▼                             ▼             │
     ┌──────────┐                 ┌──────────┐        │
     │processing│ ───────────────→│  error   │ ───────┘
     └────┬─────┘                 └──────────┘     (retry)
          │
          ▼
     ┌──────────┐
     │extracted │
     └────┬─────┘
          │
          ▼
     ┌──────────┐
     │ indexed  │
     └──────────┘
```

## 错误处理

```python
class PipelineProcessor:
    """管线处理器"""
    
    async def process(self, file_id: str) -> ProcessingResult:
        try:
            # 记录开始
            await self.log_stage(file_id, "started")
            
            # 执行各阶段
            for stage in self.stages:
                try:
                    await self.log_stage(file_id, stage.name, "started")
                    result = await stage.execute(file_id)
                    await self.log_stage(file_id, stage.name, "completed")
                except StageError as e:
                    await self.log_stage(file_id, stage.name, "failed", str(e))
                    if stage.required:
                        raise
                    # 可选阶段失败，继续执行
            
            await self.update_status(file_id, "completed")
            return ProcessingResult(success=True)
            
        except Exception as e:
            await self.update_status(file_id, "error", str(e))
            return ProcessingResult(success=False, error=str(e))
```

## 性能优化

### 并行处理

```python
# 并行处理多个页面的 OCR
async def parallel_ocr(pages: list[PageResult]) -> list[PageResult]:
    semaphore = asyncio.Semaphore(4)  # 限制并发
    
    async def process_with_limit(page):
        async with semaphore:
            return await ocr_processor.process_page(page)
    
    return await asyncio.gather(*[
        process_with_limit(page) 
        for page in pages if page.needs_ocr
    ])
```

### 批量嵌入

```python
# 批量生成嵌入而不是逐个生成
embeddings = await embedding_service.embed([
    chunk.content for chunk in chunks
])
```

### 流式处理

```python
# 大文件流式处理
async def stream_process_large_file(file_path: str):
    async for page in pdf_streamer.stream(file_path):
        # 处理单页
        result = await process_page(page)
        yield result
```

## 下一步

- [数据库架构](./database-schema.md) - 了解数据存储设计
- [存储架构](./storage-architecture.md) - 了解文件存储设计
