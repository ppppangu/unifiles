from typing import Optional
from pydantic import BaseModel


class UploadRequest(BaseModel):
    """文件上传请求"""
    user_id: str = "default"


class ProcessRequest(BaseModel):
    """文件处理请求"""
    user_id: str
    file_url: str
    knowledge_base_id: Optional[str] = None
    mode: str = "simple"


class DeleteRequest(BaseModel):
    """文件删除请求"""
    user_id: str
    file_id: str
    knowledge_base_id: Optional[str] = None


class GraphRequest(BaseModel):
    """图谱操作请求"""
    user_id: str
    knowledge_base_id: str
    mode: str  # "produce" or "get"
    level: str  # "document" or "subject"