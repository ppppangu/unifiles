from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    chunk_strategy: str = Field(
        default="semantic", description="分块策略: semantic|fixed|sliding"
    )


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
