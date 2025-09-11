"""
File Server v1 API - RESTful Architecture
符合RESTful和Python Web标准的文件服务器API

主要资源域：
1. Files - 文件存储和管理
2. Knowledge Bases - 知识库操作和文档处理

启动命令：uv run uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
"""

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Path as FastAPIPath
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg
from minio import Minio
import io
from server.core.utils.tools import detect_content_type

# 导入中间件
from .middlewares import ClientIPMiddleware, FileValidationMiddleware, AuthMiddleware

# 导入配置工具
from server.core.utils.tools import (
    read_config,
    read_pg_config,
    read_minio_config,
    mk_need_path,
    detect_content_type
)

# 导入数据模型
from pydantic import BaseModel, Field
import uuid
import httpx


# ==================== 数据模型定义 ====================

# ========== Files 资源相关模型 ==========
class FileInfo(BaseModel):
    """文件信息模型"""
    file_id: str = Field(description="文件唯一标识")
    filename: str = Field(description="原始文件名")
    file_size: int = Field(description="文件大小（字节）")
    content_type: str = Field(description="文件类型")
    public_url: str = Field(description="公网访问URL")
    object_path: str = Field(description="存储路径")
    created_at: str = Field(description="上传时间")

class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    file: FileInfo = Field(description="文件信息")

class SupportedFileTypes(BaseModel):
    """支持的文件类型响应"""
    document_types: List[str] = Field(description="文档类型")
    pdf_types: List[str] = Field(description="PDF类型")
    code_types: List[str] = Field(description="代码类型")
    all_types: List[str] = Field(description="所有支持类型")

# ========== Files 资源相关模型（内容提取）==========
class FileExtractRequest(BaseModel):
    """文件内容提取请求"""
    mode: str = Field(default="simple", description="提取模式: simple|normal|ocr")
    
class ExtractedContent(BaseModel):
    """提取的文件内容"""
    file_id: str = Field(description="文件ID")
    extraction_id: str = Field(description="提取任务ID")
    content_type: str = Field(description="内容类型")
    extracted_text: Optional[str] = Field(description="提取的文本内容")
    markdown_content: Optional[str] = Field(description="Markdown格式内容")
    structured_data: Optional[Dict[str, Any]] = Field(description="结构化数据")
    extraction_metadata: Dict[str, Any] = Field(description="提取元数据")
    status: str = Field(description="提取状态")
    created_at: str = Field(description="提取时间")
    
class FileExtractResponse(BaseModel):
    """文件内容提取响应"""
    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    extracted_content: ExtractedContent = Field(description="提取的内容信息")

# ========== Knowledge Bases 资源相关模型 ==========
class ProcessDocumentRequest(BaseModel):
    """处理文档到知识库请求"""
    extraction_id: str = Field(description="文件提取结果ID")
    knowledge_base_id: str = Field(description="目标知识库ID")
    chunk_strategy: str = Field(default="semantic", description="分块策略: semantic|fixed|sliding")

class ProcessedDocument(BaseModel):
    """已处理的文档信息"""
    document_id: str = Field(description="文档ID")
    extraction_id: str = Field(description="提取结果ID")
    knowledge_base_id: str = Field(description="知识库ID")
    chunk_count: int = Field(description="分块数量")
    indexing_status: str = Field(description="索引状态")
    created_at: str = Field(description="处理时间")

class ProcessDocumentResponse(BaseModel):
    """处理文档响应"""
    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    document: ProcessedDocument = Field(description="处理后的文档信息")

class KnowledgeBaseInfo(BaseModel):
    """知识库信息"""
    kb_id: str = Field(description="知识库ID")
    user_id: str = Field(description="所属用户ID")
    document_count: int = Field(description="文档数量")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")

# ========== 通用响应模型 ==========
class StandardResponse(BaseModel):
    """标准响应模型"""
    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="响应数据")

class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    details: Optional[Dict[str, Any]] = Field(default=None, description="错误详情")


# ==================== 应用初始化 ====================

# 读取配置
config = read_config()
pg_config = read_pg_config()
minio_config = read_minio_config()

# 日志配置
log_path = Path(__file__).parent / "logs"
log_path.mkdir(exist_ok=True)
logger.add(log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")

# 支持的文件类型
DOCUMENT_FILE_TYPES = [
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", 
    ".odt", ".ods", ".odp", ".txt", ".rtf", ".jpg", 
    ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".html", 
    ".htm", ".md", ".csv", ".tsv", ".xml"
]

PDF_FILE_TYPES = [".pdf"]
CODE_FILE_TYPES = [".py", ".ipynb", ".js", ".json"]
SUPPORTED_FILE_TYPES = DOCUMENT_FILE_TYPES + PDF_FILE_TYPES + CODE_FILE_TYPES


async def startup_operations():
    """应用启动时的初始化操作"""
    try:
        # 创建必要的目录
        mk_need_path()
        logger.info("File server v1 started successfully")
        
        # 这里可以添加数据库连接检查等初始化逻辑
        # await check_database_connection()
        # await check_minio_connection()
        
    except Exception as e:
        logger.error(f"启动初始化失败: {str(e)}")
        # 继续启动，不让初始化问题阻止服务启动


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    await startup_operations()
    yield
    # 关闭时执行（如果需要的话）
    logger.info("File server v1 shutting down")


# 创建FastAPI应用实例
app = FastAPI(
    title="File Server v1 API",
    description="优化版本的文件服务器API - 支持JSON请求格式",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 添加客户端IP中间件
app.add_middleware(ClientIPMiddleware)

# 添加认证中间件（必须在文件检测中间件之前）
app.add_middleware(AuthMiddleware)

# 添加文件检测中间件
app.add_middleware(FileValidationMiddleware)


# ==================== 工具函数 ====================


async def record_file_to_database(
    file_id: str,
    user_id: str,
    filename: str,
    file_size: int,
    content_type: str,
    object_path: str,
    public_url: str
) -> None:
    """将文件信息记录到数据库"""
    try:
        # 确保用户存在
        await ensure_user_exists(user_id)
        
        # 记录文件信息
        conn = await asyncpg.connect(**pg_config)
        try:
            await conn.execute(
                """
                INSERT INTO chunk_schema.files (
                    id, user_id, bytes, filename, mime_type, 
                    file_path, raw_file_public_url, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                file_id, user_id, file_size, filename, content_type,
                object_path, public_url, "uploaded"
            )
            logger.info(f"File record created in database: {file_id}")
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error recording file to database: {str(e)}")
        raise


async def ensure_user_exists(user_id: str) -> None:
    """确保用户在数据库中存在"""
    conn = await asyncpg.connect(**pg_config)
    try:
        # 检查用户是否存在
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.users WHERE id = $1)",
            user_id
        )
        
        if not exists:
            # 创建用户
            await conn.execute(
                "INSERT INTO chunk_schema.users (id) VALUES ($1)",
                user_id
            )
            logger.info(f"Created new user: {user_id}")
    finally:
        await conn.close()


# ==================== RESTful 路由定义 ====================

# ========== 系统健康检查 ==========
@app.get("/health", response_model=StandardResponse, tags=["System"])
async def health_check():
    """系统健康检查"""
    return StandardResponse(
        success=True,
        message="Service is healthy",
        data={"version": "1.0.0", "service": "file-server-v1"}
    )


# ========== Files 资源路由 ==========
@app.get("/files/types", response_model=SupportedFileTypes, tags=["Files"])
async def get_supported_file_types():
    """获取支持的文件类型"""
    return SupportedFileTypes(
        document_types=DOCUMENT_FILE_TYPES,
        pdf_types=PDF_FILE_TYPES,
        code_types=CODE_FILE_TYPES,
        all_types=SUPPORTED_FILE_TYPES
    )


@app.post("/files", response_model=FileUploadResponse, tags=["Files"])
async def upload_file(
    request: Request,
    file: UploadFile = File(...)
):
    """
    上传文件到存储
    
    - **file**: 要上传的文件
    
    返回文件信息和公网访问URL
    
    注意：文件会自动经过FileValidationMiddleware检测文件格式、大小等
    用户ID会自动从Bearer token中解析
    """
    try:
        client_ip = request.state.client_ip
        user_id = request.state.user_id  # 从Bearer token中解析
        logger.info(f"POST /files request from {client_ip}, user_id: {user_id}, filename: {file.filename}")
        
        # 验证文件类型
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No filename provided"
            )
            
        file_type = Path(file.filename).suffix.lower()
        if file_type not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_type}. Supported types: {SUPPORTED_FILE_TYPES}"
            )
            
        # 读取文件内容并验证
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file provided"
            )
            
        logger.info(f"File info - name: {file.filename}, size: {file_size} bytes")
        
        # 生成文件ID和对象路径
        file_id = f"file-{str(uuid.uuid4())}"
        object_path = f"{user_id}/default_file_space/{file_id}/{file.filename}"
        
        # 创建MinIO客户端
        minio_client = Minio(
            minio_config['address'] if 'address' in minio_config else f"{minio_config['host']}:{int(minio_config['port'])}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False  # 根据配置调整
        )
        
        # 检查桶是否存在，不存在则创建
        bucket_name = minio_config["bucket_name"]
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
            
        # 设置Content-Type
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            content_type = detect_content_type(file.filename)
            
        # 上传文件到MinIO
        minio_client.put_object(
            bucket_name,
            object_path,
            io.BytesIO(file_content),
            length=file_size,
            content_type=content_type,
            part_size=10 * 1024 * 1024  # 10MB 分片
        )
        
        logger.info(f"File uploaded successfully to MinIO: {object_path}")
        
        # 生成公网URL
        if minio_config.get("use_public_url", False) and minio_config.get("public_url_prefix"):
            public_url = f"{minio_config['public_url_prefix']}/{bucket_name}/{object_path}"
        else:
            # 使用address或者向后兼容host:port
            if 'address' in minio_config:
                public_url = f"http://{minio_config['address']}/{bucket_name}/{object_path}"
            else:
                public_url = f"http://{minio_config['host']}:{minio_config['port']}/{bucket_name}/{object_path}"
            
        logger.info(f"Generated public URL: {public_url}")
        
        # 记录文件信息到数据库
        await record_file_to_database(
            file_id=file_id,
            user_id=user_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            object_path=object_path,
            public_url=public_url
        )
        
        # 构造返回的文件信息
        file_info = FileInfo(
            file_id=file_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            public_url=public_url,
            object_path=object_path,
            created_at=datetime.now().isoformat()
        )
        
        return FileUploadResponse(
            success=True,
            message="File uploaded successfully",
            file=file_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@app.get("/files/{file_id}", response_model=FileInfo, tags=["Files"])
async def get_file_info(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID")
):
    """
    获取文件信息
    
    根据文件ID获取文件的详细信息
    """
    try:
        client_ip = request.state.client_ip
        logger.info(f"GET /files/{file_id} request from {client_ip}")
        
        conn = await asyncpg.connect(**pg_config)
        try:
            file_record = await conn.fetchrow(
                """
                SELECT id, filename, bytes, mime_type, raw_file_public_url, 
                       file_path, created_at
                FROM chunk_schema.files 
                WHERE id = $1
                """,
                file_id
            )
            
            if not file_record:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {file_id}"
                )
                
            return FileInfo(
                file_id=file_record['id'],
                filename=file_record['filename'],
                file_size=file_record['bytes'],
                content_type=file_record['mime_type'],
                public_url=file_record['raw_file_public_url'],
                object_path=file_record['file_path'],
                created_at=file_record['created_at'].isoformat()
            )
            
        finally:
            await conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file info: {str(e)}"
        )


@app.post("/files/{file_id}/extract", response_model=FileExtractResponse, tags=["Files"])
async def extract_file_content(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    extract_request: FileExtractRequest = FileExtractRequest()
):
    """
    提取文件内容
    
    支持多种提取模式：
    - simple: 基础文本提取
    - normal: 标准文档解析 
    - ocr: OCR图像文字识别
    
    支持多种输出格式：
    - text: 纯文本
    - markdown: Markdown格式
    - structured: 结构化数据
    """
    try:
        client_ip = request.state.client_ip
        user_id = request.state.user_id
        logger.info(f"POST /files/{file_id}/extract from {client_ip}, user: {user_id}")
        logger.info(f"Extract request: {extract_request.dict()}")
        
        # 获取文件信息
        conn = await asyncpg.connect(**pg_config)
        try:
            file_record = await conn.fetchrow(
                """
                SELECT id, filename, raw_file_public_url, user_id, mime_type
                FROM chunk_schema.files 
                WHERE id = $1
                """,
                file_id
            )
            
            if not file_record:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {file_id}"
                )
                
            # 验证用户权限
            if file_record['user_id'] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: file belongs to another user"
                )
                
        finally:
            await conn.close()
        
        # TODO: 实现实际的内容提取逻辑
        # 这里应该调用 OCR Pipeline 或文档解析服务
        # 根据 extract_request.mode 和 extract_request.extract_type 选择处理方式
        
        # 暂时返回模拟响应
        extraction_id = f"extract_{str(uuid.uuid4())[:8]}"
        
        extracted_content = ExtractedContent(
            file_id=file_id,
            extraction_id=extraction_id,
            content_type=extract_request.extract_type,
            extracted_text=f"[模拟提取内容] 文件 {file_record['filename']} 的文本内容",
            markdown_content=None if extract_request.extract_type != "markdown" else f"# {file_record['filename']}\n\n模拟Markdown内容",
            structured_data=None if extract_request.extract_type != "structured" else {"pages": 1, "words": 100},
            extraction_metadata={
                "mode": extract_request.mode,
                "file_type": file_record['mime_type'],
                "processing_time": "0.5s"
            },
            status="completed",
            created_at=datetime.now().isoformat()
        )
        
        return FileExtractResponse(
            success=True,
            message="File content extracted successfully",
            extracted_content=extracted_content
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting file content: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Content extraction failed: {str(e)}"
        )


@app.delete("/files/{file_id}", response_model=StandardResponse, tags=["Files"])
async def delete_file(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID")
):
    """
    删除文件
    
    从存储中删除指定的文件
    """
    try:
        client_ip = request.state.client_ip
        user_id = request.state.user_id  # 从Bearer token中解析
        logger.info(f"DELETE /files/{file_id} request from {client_ip}, user_id: {user_id}")
        
        conn = await asyncpg.connect(**pg_config)
        try:
            # 获取文件信息
            file_record = await conn.fetchrow(
                """
                SELECT id, user_id, file_path
                FROM chunk_schema.files 
                WHERE id = $1
                """,
                file_id
            )
            
            if not file_record:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {file_id}"
                )
                
            # 验证用户权限
            if file_record['user_id'] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: file belongs to another user"
                )
            
            minio_client = Minio(
                minio_config['address'] if 'address' in minio_config else f"{minio_config['host']}:{int(minio_config['port'])}",
                access_key=minio_config["access_key"],
                secret_key=minio_config["secret_key"],
                secure=False
            )
            
            bucket_name = minio_config["bucket_name"]
            object_path = file_record['file_path']
            
            try:
                minio_client.remove_object(bucket_name, object_path)
                logger.info(f"File deleted from MinIO: {object_path}")
            except Exception as minio_error:
                logger.warning(f"Failed to delete file from MinIO: {str(minio_error)}")
                # 继续执行数据库删除，但记录警告
                
            # 从数据库删除记录
            await conn.execute(
                "DELETE FROM chunk_schema.files WHERE id = $1",
                file_id
            )
            
            logger.info(f"File deleted successfully: {file_id}")
            
            return StandardResponse(
                success=True,
                message="File deleted successfully",
                data={"file_id": file_id}
            )
            
        finally:
            await conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )


# ========== Knowledge Bases 资源路由 ==========
@app.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseInfo, tags=["Knowledge Bases"])
async def get_knowledge_base_info(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID")
):
    """
    获取知识库信息
    
    返回知识库的基本信息和统计数据
    """
    # TODO: 实现获取知识库信息逻辑
    client_ip = request.state.client_ip
    user_id = request.state.user_id  # 从Bearer token中解析
    logger.info(f"GET /knowledge-bases/{kb_id} request from {client_ip}, user_id: {user_id}")
    
    raise HTTPException(
        status_code=501,
        detail="Get knowledge base info functionality not implemented yet"
    )


@app.post("/knowledge-bases/{kb_id}/documents", response_model=ProcessDocumentResponse, tags=["Knowledge Bases"])
async def index_extracted_content_to_knowledge_base(
    request: Request,
    process_request: ProcessDocumentRequest,
    kb_id: str = FastAPIPath(..., description="知识库ID")
):
    """
    将已提取的内容索引到知识库
    
    基于文件提取结果，将内容分块并索引到指定知识库
    
    - **extraction_id**: 文件提取结果ID
    - **knowledge_base_id**: 目标知识库ID
    - **chunk_strategy**: 分块策略 (semantic|fixed|sliding)
    """
    try:
        client_ip = request.state.client_ip
        user_id = request.state.user_id
        
        logger.info(f"POST /knowledge-bases/{kb_id}/documents from {client_ip}, user: {user_id}")
        logger.info(f"Process request: {process_request.dict()}")
        
        # TODO: 验证 extraction_id 是否存在
        # TODO: 验证 knowledge_base_id 是否存在且用户有权限
        # TODO: 实现实际的分块和索引逻辑
        
        # 暂时返回模拟响应
        document_id = f"doc_{str(uuid.uuid4())[:8]}"
        
        processed_doc = ProcessedDocument(
            document_id=document_id,
            extraction_id=process_request.extraction_id,
            knowledge_base_id=kb_id,
            chunk_count=0,  # TODO: 实际分块数量
            indexing_status="processing",
            created_at=datetime.now().isoformat()
        )
        
        return ProcessDocumentResponse(
            success=True,
            message="Document indexing started successfully",
            document=processed_doc
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {str(e)}"
        )


@app.get("/knowledge-bases/{kb_id}/documents", response_model=List[ProcessedDocument], tags=["Knowledge Bases"])
async def get_knowledge_base_documents(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
    limit: int = 50,
    offset: int = 0
):
    """
    获取知识库文档列表
    
    返回指定知识库中的所有文档
    """
    # TODO: 实现获取文档列表逻辑
    client_ip = request.state.client_ip
    user_id = request.state.user_id  # 从Bearer token中解析
    logger.info(f"GET /knowledge-bases/{kb_id}/documents request from {client_ip}")
    logger.info(f"user_id: {user_id}, limit: {limit}, offset: {offset}")
    
    raise HTTPException(
        status_code=501,
        detail="Get knowledge base documents functionality not implemented yet"
    )


@app.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=StandardResponse, tags=["Knowledge Bases"])
async def delete_knowledge_base_document(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
    doc_id: str = FastAPIPath(..., description="文档ID")
):
    """
    删除知识库文档
    
    从知识库中删除指定文档及其向量数据
    """
    # TODO: 实现删除知识库文档逻辑
    client_ip = request.state.client_ip
    user_id = request.state.user_id  # 从Bearer token中解析
    logger.info(f"DELETE /knowledge-bases/{kb_id}/documents/{doc_id} request from {client_ip}")
    logger.info(f"user_id: {user_id}")
    
    raise HTTPException(
        status_code=501,
        detail="Delete knowledge base document functionality not implemented yet"
    )


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8088,
        reload=True,
        log_level="info"
    )