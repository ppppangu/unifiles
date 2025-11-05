"""
文档处理基础模块

定义文档处理的抽象基类和核心功能
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from server.app.v1.schemas import ExtractedContent, FileExtractRequest


class DocumentProcessor(ABC):
    """文档处理器抽象基类"""

    @abstractmethod
    async def process(
        self, file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理文档并返回结果

        Args:
            file_path: 文件路径
            options: 处理选项

        Returns:
            处理结果
        """
        pass

    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """获取支持的文件类型"""
        pass

    @abstractmethod
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        pass


class BaseDocumentProcessor(DocumentProcessor):
    """基础文档处理器实现"""

    def __init__(self):
        self.processor_name = "base_processor"

    def get_processor_name(self) -> str:
        return self.processor_name

    def get_supported_types(self) -> List[str]:
        return ["text/plain", "application/octet-stream"]

    async def process(
        self, file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """基础处理实现"""
        logger.info(f"Processing file with base processor: {file_path}")

        return {
            "processor": self.processor_name,
            "file_path": file_path,
            "status": "processed",
            "options": options or {},
        }


def process_file_content(
    file_id: str,
    file_record: dict,
    extract_request: FileExtractRequest,
) -> ExtractedContent:
    """
    处理文件内容提取的核心逻辑

    兼容现有API的处理函数，未来将被新的处理器架构替代

    Args:
        file_id: 文件ID
        file_record: 从数据库获取的文件记录
        extract_request: 内容提取的请求参数

    Returns:
        提取的内容信息
    """
    logger.info(
        f"Processing file content for {file_id} with mode '{extract_request.mode}'"
    )

    # TODO: 实现实际的内容提取逻辑
    # 这里应该调用 OCR Pipeline 或文档解析服务
    # 根据 extract_request.mode 选择处理方式

    # 暂时返回模拟响应
    extraction_id = f"extract_{str(uuid.uuid4())[:8]}"

    # 假设内容类型
    assumed_content_type = "text/plain"

    extracted_content = ExtractedContent(
        file_id=file_id,
        extraction_id=extraction_id,
        content_type=assumed_content_type,
        extracted_text=f"[模拟提取内容] 文件 {file_record['filename']} 的文本内容",
        markdown_content=f"# {file_record['filename']}\n\n模拟Markdown内容",
        structured_data={"pages": 1, "words": 100},
        extraction_metadata={
            "mode": extract_request.mode,
            "file_type": file_record["mime_type"],
            "processing_time": "0.5s",
        },
        status="completed",
        created_at=datetime.now().isoformat(),
    )

    logger.info(f"Mock content extraction complete for file: {file_id}")
    return extracted_content
