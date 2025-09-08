from typing import Any, List, Optional, Dict
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """基础响应模型"""
    status: str
    message: str


class HealthResponse(BaseResponse):
    """健康检查响应"""
    pass


class SupportedFileTypesResponse(BaseResponse):
    """支持的文件类型响应"""
    data: Dict[str, List[str]]


class UploadResponse(BaseResponse):
    """文件上传响应"""
    data: Dict[str, Any]


class ProcessFileData(BaseModel):
    """文件处理响应数据"""
    user_id: str
    knowledge_base_id: str
    mode: str
    file_url: str
    file_uuid: str
    markdown_public_url: str = ""
    pdf_file_public_url: str = ""


class ProcessResponse(BaseResponse):
    """文件处理响应"""
    data: ProcessFileData


class DeleteResponse(BaseResponse):
    """文件删除响应"""
    pass


class GraphData(BaseModel):
    """图谱数据"""
    pass  # 根据具体图谱数据结构定义


class GraphResponse(BaseResponse):
    """图谱操作响应"""
    data: Optional[GraphData] = None