"""
格式验证和PDF转换流水线
负责文件格式验证和转换为PDF格式的处理
"""

from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from unifiles.core.logging import get_logger

from ..config.env_config import read_config
from ..utils.file_utils import detect_content_type


class FileFormatValidator:
    """文件格式验证器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        # 统一使用应用日志，保证控制台/文件输出
        global logger
        logger = get_logger()

        # 支持的文件类型定义
        self.DOCUMENT_FILE_TYPES = [
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".odt",
            ".ods",
            ".odp",
            ".txt",
            ".rtf",
            ".jpg",
            ".jpeg",
            ".png",
            ".tiff",
            ".tif",
            ".bmp",
            ".html",
            ".htm",
            ".md",
            ".csv",
            ".tsv",
            ".xml",
        ]
        self.PDF_FILE_TYPES = [".pdf"]
        self.CODE_FILE_TYPES = [".py", ".ipynb", ".js", ".json"]
        self.SUPPORTED_FILE_TYPES = (
            self.DOCUMENT_FILE_TYPES + self.PDF_FILE_TYPES + self.CODE_FILE_TYPES
        )

    def validate_file_type(self, filename: str) -> bool:
        """验证文件类型是否支持"""
        if not filename:
            return False

        file_extension = Path(filename).suffix.lower()
        is_supported = file_extension in self.SUPPORTED_FILE_TYPES

        if not is_supported:
            logger.warning(f"Unsupported file type: {file_extension}")
        else:
            logger.info(f"File type validated: {file_extension}")

        return is_supported

    def is_pdf_file(self, filename: str) -> bool:
        """检查文件是否为PDF格式"""
        return Path(filename).suffix.lower() in self.PDF_FILE_TYPES

    def is_document_file(self, filename: str) -> bool:
        """检查文件是否为文档格式（需要转换的格式）"""
        return Path(filename).suffix.lower() in self.DOCUMENT_FILE_TYPES

    def get_file_category(self, filename: str) -> str:
        """获取文件类别"""
        extension = Path(filename).suffix.lower()

        if extension in self.PDF_FILE_TYPES:
            return "pdf"
        if extension in self.DOCUMENT_FILE_TYPES:
            return "document"
        if extension in self.CODE_FILE_TYPES:
            return "code"
        return "unknown"

    async def validate_file_content(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """验证文件内容"""
        validation_result = {
            "is_valid": False,
            "file_size": len(file_content),
            "content_type": detect_content_type(filename),
            "category": self.get_file_category(filename),
            "errors": [],
        }

        # 检查文件是否为空
        if len(file_content) == 0:
            validation_result["errors"].append("File is empty")
            return validation_result

        # 检查文件大小限制（可配置）
        max_file_size = self.config.get("file_limits", {}).get(
            "max_file_size", 100 * 1024 * 1024
        )  # 默认100MB
        if len(file_content) > max_file_size:
            validation_result["errors"].append(
                f"File size ({len(file_content)} bytes) exceeds limit ({max_file_size} bytes)"
            )
            return validation_result

        # 基本的文件头验证（可扩展）
        if self.is_pdf_file(filename):
            if not file_content.startswith(b"%PDF-"):
                validation_result["errors"].append("Invalid PDF file header")
                return validation_result

        validation_result["is_valid"] = True
        logger.info(
            f"File content validated: {filename}, size: {len(file_content)} bytes"
        )

        return validation_result


class PDFConverter:
    """PDF转换器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.validator = FileFormatValidator(config)
        # 统一使用应用日志
        global logger
        logger = get_logger()

    def _fix_public_url(self, original_url: str) -> str:
        """修正公网URL"""
        try:
            public_prefix = self.config["server_components"]["minio"].get(
                "public_url_prefix"
            )
            if not public_prefix:
                return original_url
            if original_url.startswith(public_prefix):
                return original_url

            from urllib.parse import urlparse

            parsed = urlparse(original_url)
            fixed = f"{public_prefix}{parsed.path}"
            logger.info(f"Fixed URL from {original_url} to {fixed}")
            return fixed
        except Exception as e:
            logger.warning(f"URL fixing failed: {e}")
            return original_url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    )
    async def convert_document_to_pdf(self, file_url: str) -> Optional[str]:
        """
        将文档转换为PDF格式

        Args:
            file_url: 文件的公网URL

        Returns:
            转换后的PDF文件URL，失败时返回None
        """
        try:
            # 验证URL格式
            if not file_url or not isinstance(file_url, str):
                logger.error(f"Invalid file URL: {file_url}")
                return None

            # 从URL中正确提取文件名（去除查询参数）
            from urllib.parse import unquote, urlparse

            parsed_url = urlparse(file_url)
            # 获取URL路径的最后一部分作为文件名
            url_path = unquote(parsed_url.path)  # 解码URL编码
            filename = url_path.split("/")[-1] if "/" in url_path else url_path

            logger.info(f"Extracted filename from URL: {filename}")

            # 提取文件扩展名
            file_extension = Path(filename).suffix.lower()
            logger.info(f"Detected file extension: {file_extension}")

            # 如果已经是PDF，直接返回修正后的URL
            if file_extension == ".pdf":
                logger.info(
                    f"File is already PDF format, no conversion needed: {filename}"
                )
                return self._fix_public_url(file_url)

            # 检查是否为支持的文档格式
            if not self.validator.is_document_file(filename):
                logger.error(f"Unsupported file type for conversion: {file_extension}")
                return None

            # 调用转换服务
            logger.info(f"Starting document conversion: {file_url}")
            convert_url = self.config["convert_format_server"][0]["url"] + "/convert"
            logger.info(f"Conversion service URL: {convert_url}")

            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                response = await client.post(convert_url, data={"file_url": file_url})
                response.raise_for_status()
                result = response.json()

                if "converted_url" not in result or not result["converted_url"]:
                    logger.error(
                        f"Conversion service returned invalid result: {result}"
                    )
                    return None

                converted_url = result["converted_url"]
                logger.info(
                    f"Document conversion successful: {file_url} -> {converted_url}"
                )
                converted_url = self._fix_public_url(converted_url)
                return converted_url

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Conversion service HTTP error: {e.response.status_code} - {e.response.reason_phrase}"
            )
            if e.response.status_code == 400:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Conversion service error details: {error_detail}")
                except Exception:
                    pass
            raise
        except httpx.RequestError as e:
            logger.error(f"Conversion service request error: {e!s}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file conversion: {e!s}")
            return None


class FormatValidationPipeline:
    """格式验证和PDF转换流水线"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.validator = FileFormatValidator(config)
        self.converter = PDFConverter(config)

    async def process_file(
        self, filename: str, file_content: bytes, file_url: str
    ) -> Dict[str, Any]:
        """
        处理文件：验证格式并转换为PDF

        Args:
            filename: 文件名
            file_content: 文件内容（用于验证）
            file_url: 文件URL（用于转换）

        Returns:
            处理结果字典
        """
        result = {
            "success": False,
            "original_url": file_url,
            "pdf_url": None,
            "validation": None,
            "conversion": None,
            "errors": [],
        }

        try:
            # 第一步：格式验证
            logger.info(f"Step 1: Validating file format for {filename}")

            if not self.validator.validate_file_type(filename):
                result["errors"].append(
                    f"Unsupported file type: {Path(filename).suffix}"
                )
                return result

            validation_result = await self.validator.validate_file_content(
                file_content, filename
            )
            result["validation"] = validation_result

            if not validation_result["is_valid"]:
                result["errors"].extend(validation_result["errors"])
                return result

            logger.info(f"File format validation passed for {filename}")

            # 第二步：PDF转换（如果需要）
            logger.info(f"Step 2: Processing PDF conversion for {filename}")

            if self.validator.is_pdf_file(filename):
                # 已经是PDF，直接使用原URL
                result["pdf_url"] = self.converter._fix_public_url(file_url)
                result["conversion"] = {
                    "needed": False,
                    "message": "File is already in PDF format",
                }
                logger.info(f"No conversion needed for PDF file: {filename}")
            else:
                # 需要转换
                converted_url = await self.converter.convert_document_to_pdf(file_url)

                if converted_url:
                    result["pdf_url"] = converted_url
                    result["conversion"] = {
                        "needed": True,
                        "success": True,
                        "original_url": file_url,
                        "converted_url": converted_url,
                    }
                    logger.info(f"Document converted successfully: {filename}")
                else:
                    result["errors"].append("Document conversion failed")
                    result["conversion"] = {
                        "needed": True,
                        "success": False,
                        "message": "Conversion service failed",
                    }
                    return result

            result["success"] = True
            logger.info(
                f"Format validation and PDF conversion pipeline completed for {filename}"
            )

        except Exception as e:
            error_msg = f"Pipeline processing failed: {e!s}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    async def process_file_url_only(self, file_url: str) -> Dict[str, Any]:
        """
        仅处理文件URL（不验证内容）

        Args:
            file_url: 文件URL

        Returns:
            处理结果字典
        """
        filename = file_url.split("/")[-1] if "/" in file_url else file_url

        result = {
            "success": False,
            "original_url": file_url,
            "pdf_url": None,
            "validation": {
                "is_valid": True,
                "category": self.validator.get_file_category(filename),
                "note": "Content validation skipped - URL only processing",
            },
            "conversion": None,
            "errors": [],
        }

        try:
            # 仅验证文件类型
            if not self.validator.validate_file_type(filename):
                result["errors"].append(
                    f"Unsupported file type: {Path(filename).suffix}"
                )
                return result

            # PDF转换处理
            if self.validator.is_pdf_file(filename):
                result["pdf_url"] = self.converter._fix_public_url(file_url)
                result["conversion"] = {
                    "needed": False,
                    "message": "File is already in PDF format",
                }
            else:
                converted_url = await self.converter.convert_document_to_pdf(file_url)

                if converted_url:
                    result["pdf_url"] = converted_url
                    result["conversion"] = {
                        "needed": True,
                        "success": True,
                        "original_url": file_url,
                        "converted_url": converted_url,
                    }
                else:
                    result["errors"].append("Document conversion failed")
                    result["conversion"] = {
                        "needed": True,
                        "success": False,
                        "message": "Conversion service failed",
                    }
                    return result

            result["success"] = True

        except Exception as e:
            error_msg = f"URL-only pipeline processing failed: {e!s}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result
