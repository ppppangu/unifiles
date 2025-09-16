import uuid
from datetime import datetime

from loguru import logger

from server.app.v1.schemas import ExtractedContent, FileExtractRequest


def process_file_content(
    file_id: str,
    file_record: dict,  # Assuming this is the record fetched from DB
    extract_request: FileExtractRequest,
) -> ExtractedContent:
    """
    处理文件内容提取的核心逻辑。
    目前返回模拟数据，未来将集成真实的文档解析和OCR服务。

    :param file_id: 文件ID。
    :param file_record: 从数据库获取的文件记录。
    :param extract_request: 内容提取的请求参数。
    :return: 提取的内容信息。
    """
    logger.info(
        f"Processing file content for {file_id} with mode '{extract_request.mode}'"
    )

    # TODO: 实现实际的内容提取逻辑
    # 这里应该调用 OCR Pipeline 或文档解析服务
    # 根据 extract_request.mode 选择处理方式

    # 暂时返回模拟响应
    extraction_id = f"extract_{str(uuid.uuid4())[:8]}"

    # Note: The original code referenced a non-existent 'extract_type' field.
    # We are simplifying the mock response for now.
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
