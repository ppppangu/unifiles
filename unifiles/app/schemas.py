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
    public_url: str = Field(description="原始文件访问URL")
    object_path: str = Field(description="原始文件存储路径")
    is_public: bool = Field(description="是否公开访问")
    created_at: str = Field(description="上传时间")
    # PDF转换相关字段
    original_filename: Optional[str] = Field(
        default=None, description="转换前的原始文件名（兼容字段）"
    )
    is_converted: bool = Field(default=False, description="是否已转换为PDF")
    conversion_status: Optional[str] = Field(
        default=None, description="转换状态: success|failed|skipped"
    )
    derived_pdf_url: Optional[str] = Field(
        default=None, description="派生PDF访问URL（如有转换）"
    )


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


class FileListRequest(BaseModel):
    """文件列表请求参数"""

    limit: Optional[int] = Field(default=50, description="返回数量限制", ge=1, le=100)
    offset: Optional[int] = Field(default=0, description="分页偏移量", ge=0)


class FileListResponse(BaseModel):
    """文件列表响应模型"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    files: List[FileInfo] = Field(description="文件列表")
    total_count: Optional[int] = Field(description="总文件数量")
    has_more: bool = Field(description="是否有更多文件")


# ========== Files 资源相关模型（内容提取）==========
class FileExtractRequest(BaseModel):
    """文件内容提取请求"""

    mode: str = Field(
        default="simple", description="提取模式: simple|ocr_provider_name"
    )
    parse_image_content: bool = Field(
        default=False,
        description="是否解析图像内容到full_markdown(仅对支持的OCR提供商有效,如selfhosted)",
    )


class ExtractedContent(BaseModel):
    """提取的文件内容"""

    file_id: str = Field(description="文件ID")
    extraction_id: str = Field(
        description="提取文档ID（数据库中的extracted_documents表主键）"
    )
    content_type: str = Field(description="内容类型")
    extracted_text: Optional[str] = Field(description="提取的文本内容")
    markdown_content: Optional[str] = Field(description="Markdown格式内容")
    structured_data: Optional[Dict[str, Any]] = Field(description="结构化数据")
    extraction_metadata: Dict[str, Any] = Field(description="提取元数据")
    extraction_strategy: Optional[str] = Field(
        default=None, description="使用的提取策略"
    )
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
    chunk_strategy: str = Field(
        default="markdown_hierarchical",
        description="分块策略: markdown_hierarchical|fixed|semantic",
    )


class KnowledgeBaseInfo(BaseModel):
    """知识库信息"""

    kb_id: str = Field(description="知识库ID")
    name: str = Field(description="知识库名称")
    description: Optional[str] = Field(description="知识库描述")
    user_id: str = Field(description="所属用户ID")
    document_count: int = Field(description="文档数量")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求"""

    name: str = Field(..., min_length=1, max_length=128, description="知识库名称")
    description: Optional[str] = Field(default="", description="知识库描述")


class KnowledgeBaseCreateResponse(BaseModel):
    """创建知识库响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    knowledge_base: KnowledgeBaseInfo = Field(description="知识库信息")


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    knowledge_bases: List[KnowledgeBaseInfo] = Field(description="知识库列表")
    total_count: int = Field(description="总数量")
    has_more: bool = Field(description="是否有更多数据")


class ProcessedDocument(BaseModel):
    """处理后的文档信息"""

    document_id: str = Field(description="文档ID")
    extraction_id: str = Field(description="提取ID")
    knowledge_base_id: str = Field(description="知识库ID")
    chunk_count: int = Field(description="分块数量")
    indexing_status: str = Field(description="索引状态")
    created_at: str = Field(description="创建时间")


class ProcessDocumentResponse(BaseModel):
    """处理文档响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    document: ProcessedDocument = Field(description="处理后的文档信息")


class KnowledgeBaseDocumentsResponse(BaseModel):
    """知识库文档列表响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    documents: List[ProcessedDocument] = Field(description="文档列表")
    total_count: Optional[int] = Field(default=None, description="总文档数量")
    has_more: bool = Field(description="是否有更多数据")


# ========== Knowledge Base Search 检索相关模型 ==========
class SearchRequest(BaseModel):
    """知识库检索请求"""

    query: str = Field(..., min_length=1, description="检索查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    include_photos: bool = Field(
        default=False, description="是否包含图片块在检索结果中"
    )


class SearchResultItem(BaseModel):
    """单个检索结果"""

    component_id: str = Field(description="组件ID（统一主键）")
    document_id: str = Field(description="文档ID")
    text_content: str = Field(description="文本内容或图片描述")
    similarity_score: float = Field(description="相似度分数 (0-1)")
    component_type: str = Field(default="chunk", description="组件类型（chunk或photo）")


class SearchResponse(BaseModel):
    """检索结果响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    results: List[SearchResultItem] = Field(description="检索结果列表")
    total_results: int = Field(description="返回结果数量")
    query: str = Field(description="原始查询")


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


# ========== User 用户相关模型 ==========
class UserCreateRequest(BaseModel):
    """用户创建请求"""

    user_id: str = Field(..., min_length=1, max_length=128, description="用户ID")
    username: Optional[str] = Field(default=None, max_length=128, description="用户名")
    email: Optional[str] = Field(default=None, max_length=256, description="邮箱")
    display_name: Optional[str] = Field(
        default=None, max_length=128, description="显示名称"
    )
    user_settings: Optional[Dict[str, Any]] = Field(
        default=None, description="用户设置"
    )


class UserInfo(BaseModel):
    """用户信息"""

    id: str = Field(description="用户ID")
    username: Optional[str] = Field(default=None, description="用户名")
    email: Optional[str] = Field(default=None, description="邮箱")
    display_name: Optional[str] = Field(default=None, description="显示名称")
    user_status: str = Field(description="用户状态")
    user_role: str = Field(description="用户角色")
    knowledge_ids: List[str] = Field(description="知识库ID列表")
    user_settings: Dict[str, Any] = Field(description="用户设置")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")
    last_login_at: Optional[str] = Field(default=None, description="最后登录时间")


class UserCreateResponse(BaseModel):
    """用户创建响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    user: UserInfo = Field(description="用户信息")


# ========== Access Key 相关模型 ==========
class AccessKeyCreateRequest(BaseModel):
    """创建访问密钥请求"""

    name: str = Field(..., min_length=1, max_length=128, description="密钥名称")
    scopes: Optional[List[str]] = Field(
        default=None, description="权限范围，如 ['read','write']"
    )
    description: Optional[str] = Field(default=None, description="密钥描述")
    expires_at: Optional[str] = Field(
        default=None, description="过期时间（RFC3339 日期时间字符串）"
    )


class AccessKeyCreateResponse(BaseModel):
    """创建访问密钥响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    key_id: Optional[str] = Field(default=None, description="访问密钥ID")
    access_key: Optional[str] = Field(default=None, description="实际的Bearer Token")


class AccessKeyInfo(BaseModel):
    """访问密钥信息（列表/详情用，不包含完整密钥值）"""

    id: str = Field(description="访问密钥ID")
    name: str = Field(description="密钥名称")
    description: Optional[str] = Field(default=None, description="密钥描述")
    scopes: List[str] = Field(description="权限范围")
    is_active: bool = Field(description="是否启用")
    created_at: str = Field(description="创建时间")
    expires_at: Optional[str] = Field(default=None, description="过期时间")
    last_used_at: Optional[str] = Field(default=None, description="最后使用时间")


class AccessKeyListResponse(BaseModel):
    """访问密钥列表响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    access_keys: List[AccessKeyInfo] = Field(description="访问密钥列表")


# ========== Async Tasks 异步任务相关模型 ==========
class TaskSubmitResponse(BaseModel):
    """异步任务提交响应"""

    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态（queued）")
    message: str = Field(description="响应消息")
    file_id: Optional[str] = Field(default=None, description="关联的文件ID")
    entity_id: Optional[str] = Field(default=None, description="关联的实体ID")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""

    task_id: str = Field(description="任务ID")
    task_type: str = Field(description="任务类型")
    status: str = Field(
        description="任务状态: pending|queued|processing|completed|failed|cancelled|timeout"
    )
    progress_percent: int = Field(description="进度百分比（0-100）")
    progress_message: Optional[str] = Field(default=None, description="当前阶段描述")
    entity_type: Optional[str] = Field(default=None, description="实体类型")
    entity_id: Optional[str] = Field(default=None, description="实体ID")
    created_at: str = Field(description="任务创建时间")
    started_at: Optional[str] = Field(default=None, description="任务开始时间")
    completed_at: Optional[str] = Field(default=None, description="任务完成时间")
    error_message: Optional[str] = Field(
        default=None, description="错误消息（如果失败）"
    )
    retry_count: Optional[int] = Field(default=0, description="已重试次数")
    max_retries: Optional[int] = Field(default=3, description="最大重试次数")


class TaskResultResponse(BaseModel):
    """任务结果响应"""

    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    result_data: Optional[Dict[str, Any]] = Field(
        default=None, description="任务结果数据"
    )
    extracted_content: Optional[ExtractedContent] = Field(
        default=None, description="提取的内容（如果是提取任务）"
    )


class TaskInfo(BaseModel):
    """任务信息（列表用）"""

    task_id: str = Field(description="任务ID")
    task_type: str = Field(description="任务类型")
    status: str = Field(description="任务状态")
    progress_percent: int = Field(description="进度百分比")
    progress_message: Optional[str] = Field(default=None, description="进度消息")
    entity_type: Optional[str] = Field(default=None, description="实体类型")
    entity_id: Optional[str] = Field(default=None, description="实体ID")
    created_at: str = Field(description="创建时间")
    started_at: Optional[str] = Field(default=None, description="开始时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    error_message: Optional[str] = Field(default=None, description="错误消息")
    priority: Optional[int] = Field(default=5, description="优先级（1-10）")


class TaskListResponse(BaseModel):
    """任务列表响应"""

    success: bool = Field(description="是否成功")
    message: str = Field(description="响应消息")
    tasks: List[TaskInfo] = Field(description="任务列表")
    total_count: int = Field(description="总任务数")
    has_more: bool = Field(description="是否有更多数据")
