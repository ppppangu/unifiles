"""
PDF处理流水线
负责PDF文件的OCR处理、Markdown提取和分层处理
包含可替换的OCR组件
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

import aiofiles
import httpx
import pdfplumber
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config.env_config import convert_to_internal_minio_url, read_config


# OCR接口定义
class OCRProvider(Protocol):
    """OCR提供者接口"""

    async def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取文本"""
        ...

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取Markdown格式文本"""
        ...

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        ...


class SimplePDFReader:
    """简单PDF读取器 - 使用pdfplumber"""

    def __init__(self):
        self.provider_name = "pdfplumber"

    def get_provider_name(self) -> str:
        return self.provider_name

    def _read_pdf_page(self, file_path: str, page_num: int = 0) -> str:
        """读取PDF指定页"""
        try:
            import warnings

            warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

            with pdfplumber.open(file_path) as pdf:
                if page_num < len(pdf.pages):
                    page = pdf.pages[page_num]
                    return page.extract_text() or ""
                return ""
        except Exception as e:
            logger.error(f"Error reading PDF page {page_num}: {e}")
            return ""

    def _get_pdf_page_count(self, file_path: str) -> int:
        """获取PDF页数"""
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"Error getting PDF page count: {e}")
            return 0

    async def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取文本"""
        try:
            # 如果是URL，先下载
            if pdf_path_or_url.startswith(("http://", "https://")):
                # 这里应该调用下载逻辑，简化处理
                logger.info(
                    f"URL processing not implemented in SimplePDFReader: {pdf_path_or_url}"
                )
                return "URL processing not supported in SimplePDFReader"

            # 获取页数
            page_count = await asyncio.to_thread(
                self._get_pdf_page_count, pdf_path_or_url
            )
            if page_count == 0:
                return ""

            # 并行读取所有页面
            tasks = [
                asyncio.to_thread(self._read_pdf_page, pdf_path_or_url, page_num)
                for page_num in range(page_count)
            ]
            results = await asyncio.gather(*tasks)

            # 合并所有页面文本
            full_text = "\n".join(filter(None, results))
            logger.info(
                f"Extracted {len(full_text)} characters from {page_count} pages"
            )

            return full_text

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取Markdown（简单实现）"""
        text = await self.extract_text_from_pdf(pdf_path_or_url)
        # 简单的文本到Markdown转换
        if text:
            return f"# PDF Content\n\n{text}"
        return ""


class MineruOCRProvider:
    """Mineru OCR提供者"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.provider_name = "mineru"

    def get_provider_name(self) -> str:
        return self.provider_name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    )
    async def request_mineru_processing(self, file_url: str) -> Optional[str]:
        """请求Mineru服务处理文件"""
        try:
            # 这里应该调用实际的Mineru服务
            # 现在返回模拟结果
            logger.info(f"Requesting Mineru processing for: {file_url}")

            # 模拟调用Mineru API
            # 实际实现应该根据Mineru的API接口来调用
            mineru_endpoint = self.config.get("mineru", {}).get(
                "endpoint", "http://localhost:8080"
            )

            async with httpx.AsyncClient(timeout=300.0) as client:  # 5分钟超时
                response = await client.post(
                    f"{mineru_endpoint}/process",
                    json={"file_url": file_url, "output_format": "markdown"},
                )
                response.raise_for_status()
                result = response.json()

                if "result_url" in result:
                    return result["result_url"]
                logger.error(f"Invalid Mineru response: {result}")
                return None

        except Exception as e:
            logger.error(f"Mineru processing failed: {e}")
            raise

    async def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        """使用Mineru从PDF提取文本"""
        try:
            result_url = await self.request_mineru_processing(pdf_path_or_url)
            if result_url:
                # 下载结果文件
                async with httpx.AsyncClient() as client:
                    response = await client.get(result_url)
                    response.raise_for_status()
                    return response.text
            return ""

        except Exception as e:
            logger.error(f"Mineru text extraction failed: {e}")
            return ""

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """使用Mineru从PDF提取Markdown"""
        return await self.extract_text_from_pdf(
            pdf_path_or_url
        )  # Mineru直接返回Markdown


class FileDownloader:
    """文件下载器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    )
    async def download_file(self, file_url: str, file_path: str) -> str:
        """
        下载文件到本地
        支持公网URL自动转换为内网地址的兜底机制
        """
        original_url = file_url

        async def _do_request(target_url: str):
            """执行真实的HTTP下载"""
            if not target_url or not target_url.startswith(("http://", "https://")):
                logger.error(f"Invalid file URL: {target_url}")
                raise ValueError(f"Invalid file URL: {target_url}")

            try:
                logger.info(f"Starting download: {target_url} to {file_path}")

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }

                timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
                limits = httpx.Limits(
                    max_keepalive_connections=50,
                    max_connections=300,
                    keepalive_expiry=30.0,
                )

                async with httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    headers=headers,
                    follow_redirects=True,
                    verify=False,
                ) as client:
                    # 先进行HEAD请求检查文件是否存在
                    try:
                        logger.info(f"Checking file accessibility: {target_url}")
                        head_response = await client.head(target_url)
                        logger.info(
                            f"HEAD request success: {head_response.status_code}, Content-Length: {head_response.headers.get('content-length', 'unknown')}"
                        )
                    except Exception as head_error:
                        logger.warning(
                            f"HEAD request failed, continuing with GET: {head_error}"
                        )

                    # 执行GET请求下载文件
                    logger.info(f"Starting GET request: {target_url}")
                    response = await client.get(target_url)

                    logger.info(f"GET response status: {response.status_code}")
                    response.raise_for_status()

                    if not response.content:
                        logger.error(f"Downloaded file content is empty: {target_url}")
                        raise ValueError(
                            f"Downloaded file content is empty: {target_url}"
                        )

                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(response.content)

                    logger.info(
                        f"File download successful: {file_path}, size: {len(response.content)} bytes"
                    )
                    return file_path

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP status error: {e.response.status_code} - {e.response.reason_phrase}"
                )
                logger.error(f"Response headers: {dict(e.response.headers)}")
                logger.error(f"Response content: {e.response.text[:500]}...")
                logger.error(f"Request URL: {target_url}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error: {e!s}, URL: {target_url}")
                logger.error(f"Error type: {type(e).__name__}")
                raise
            except Exception as e:
                logger.error(f"Unexpected download error: {e!s}, URL: {target_url}")
                logger.error(f"Error type: {type(e).__name__}")
                raise Exception(f"Download failed: {e!s}")

        # 主下载逻辑
        try:
            return await _do_request(file_url)
        except Exception as first_error:
            # 如果失败且符合公网前缀，尝试内网URL
            internal_url = convert_to_internal_minio_url(original_url)
            if internal_url != original_url:
                logger.warning(
                    f"First download failed, trying internal URL: {internal_url}"
                )
                try:
                    return await _do_request(internal_url)
                except Exception as second_error:
                    logger.error("Internal URL fallback download also failed")
                    raise second_error from first_error
            raise


class TextProcessor:
    """文本处理器 - 负责分块和分层处理"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()

    def find_all_text_and_image_index(
        self, text: str, user_id: str, knowledge_base_id: str, document_id: str
    ) -> Tuple[str, List[Tuple[int, int, str]]]:
        """
        找到文本中所有图片和文本片段的索引位置，并将相对图片路径转换为绝对MinIO URLs

        Returns:
            tuple: (converted_text, results)
                - converted_text: 转换后的markdown文本，图片路径已转换为绝对URLs
                - results: 包含元组的列表，每个元组为(开始索引, 结束索引, 类型)
        """
        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        results = []

        # 找到所有图片的位置
        image_matches = []
        for match in re.finditer(pattern, text):
            image_matches.append((match.start(), match.end(), "image"))

        # 按开始位置排序
        image_matches.sort(key=lambda x: x[0])

        # 填充文本片段
        text_length = len(text)
        current_pos = 0

        for image_start, image_end, _ in image_matches:
            # 如果当前位置到图片开始位置之间有文本，添加文本片段
            if current_pos < image_start:
                results.append((current_pos, image_start, "text"))

            # 添加图片片段
            results.append((image_start, image_end, "image"))
            current_pos = image_end

        # 处理剩余文本
        if image_matches:
            if current_pos < text_length:
                results.append((current_pos, text_length, "text"))
        # 如果没有找到任何图片，整个文本都是文本片段
        elif text_length > 0:
            results.append((0, text_length, "text"))

        # 按开始位置排序结果
        results.sort(key=lambda x: x[0])

        # 构建转换后的文本，将相对图片路径转换为绝对MinIO URLs
        converted_text = ""

        for start, end, type_ in results:
            if type_ == "text":
                converted_text += text[start:end]
            elif type_ == "image":
                image_markdown = text[start:end]
                match = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", image_markdown)
                if match:
                    alt_text = match.group(1)
                    image_path = match.group(2)

                    # 转换相对路径为绝对MinIO URL
                    if image_path.startswith("/"):
                        absolute_url = f"{self.config['server_components']['minio']['public_url_prefix']}/{self.config['server_components']['minio']['bucket_name']}/{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path[1:]}"
                    else:
                        absolute_url = f"{self.config['server_components']['minio']['public_url_prefix']}/{self.config['server_components']['minio']['bucket_name']}/{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path}"

                    converted_markdown = f"![{alt_text}]({absolute_url})"
                    converted_text += converted_markdown
                else:
                    converted_text += image_markdown

        return converted_text, results

    async def split_text(
        self, text: str, mode: str = "SlidingWindow", module: str = "normal"
    ) -> List[str]:
        """根据指定的模式和模块对文本进行分块"""
        if mode == "SlidingWindow" and module == "normal":
            chunk_size = (
                self.config.get("text_chunk_strategy", {})
                .get("SlidingWindow", {})
                .get("chunk_size", 1000)
            )
            chunk_overlap = (
                self.config.get("text_chunk_strategy", {})
                .get("SlidingWindow", {})
                .get("chunk_overlap", 200)
            )

            if len(text) <= chunk_size:
                return [text] if text.strip() else []

            new_text = []
            start = 0
            while start < len(text):
                end = start + chunk_size

                if end >= len(text):
                    chunk = text[start:]
                    if chunk.strip():
                        new_text.append(chunk)
                    break
                chunk = text[start:end]
                if chunk.strip():
                    new_text.append(chunk)

                start = end - chunk_overlap

                # 防止无限循环
                if chunk_overlap >= chunk_size:
                    start = end

            return new_text

        # 默认返回原文本作为单个块
        return [text] if text.strip() else []

    def save_results_to_json_sync(
        self, converted_text: str, results: List[Tuple[int, int, str]]
    ) -> List[Dict[str, Any]]:
        """将结果转换为字典列表"""
        results_dict = []
        for index, result in enumerate(results):
            results_dict.append(
                {
                    "content": converted_text[result[0] : result[1]],
                    "index": index,
                    "type": result[2],
                    "embedding": None,
                }
            )
        results_dict.sort(key=lambda x: x["index"])
        return results_dict

    async def process_text_content(
        self, text: str, user_id: str, knowledge_base_id: str, document_id: str
    ) -> List[Dict[str, Any]]:
        """
        处理文本内容：图片边界分块、文本分块

        Returns:
            处理后的内容列表，每个元素包含content、index、type、embedding字段
        """
        try:
            # 第一轮：以图片为分界进行分块
            logger.info("Processing text content - Step 1: Image boundary segmentation")
            converted_text, results = await asyncio.to_thread(
                self.find_all_text_and_image_index,
                text,
                user_id,
                knowledge_base_id,
                document_id,
            )
            logger.info(
                f"Image boundary segmentation completed, {len(results)} segments created"
            )

            # 转换为字典格式
            results_dict = await asyncio.to_thread(
                self.save_results_to_json_sync, converted_text, results
            )

            # 第二轮：对文本类型的内容进行进一步分块
            logger.info("Processing text content - Step 2: Text chunking")
            new_results_dict = []
            for item in results_dict:
                if item["type"] == "text":
                    text_content = item["content"]
                    text_chunks = await self.split_text(text_content)
                    for chunk in text_chunks:
                        new_results_dict.append(
                            {
                                "content": chunk,
                                "index": len(new_results_dict),
                                "type": "text",
                                "embedding": None,
                            }
                        )
                else:
                    new_results_dict.append(
                        {
                            "content": item["content"],
                            "index": len(new_results_dict),
                            "type": item["type"],
                            "embedding": None,
                        }
                    )

            logger.info(
                f"Text chunking completed, final {len(new_results_dict)} segments"
            )
            return new_results_dict

        except Exception as e:
            logger.error(f"Error processing text content: {e}")
            raise


class PDFProcessingPipeline:
    """PDF处理流水线主类"""

    def __init__(
        self,
        ocr_provider: Optional[OCRProvider] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or read_config()
        self.ocr_provider = ocr_provider or SimplePDFReader()  # 默认使用简单PDF读取器
        self.downloader = FileDownloader(config)
        self.text_processor = TextProcessor(config)

        # 创建临时目录
        self.tmp_dir = Path(__file__).parent / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

    def set_ocr_provider(self, provider: OCRProvider):
        """设置OCR提供者（支持运行时替换）"""
        self.ocr_provider = provider
        logger.info(f"OCR provider changed to: {provider.get_provider_name()}")

    async def process_pdf_simple(self, pdf_path: str) -> str:
        """简单模式：使用pdfplumber读取PDF"""
        try:
            simple_reader = SimplePDFReader()
            text = await simple_reader.extract_text_from_pdf(pdf_path)

            if not text or text.strip() == "":
                text = "这是一个占位符，用于保证边缘情况，需要图片处理走normal模式"
                logger.info(
                    "PDF appears to be image-based or empty, using placeholder text"
                )

            logger.info(
                f"Simple mode PDF processing completed, {len(text)} characters extracted"
            )
            return text

        except Exception as e:
            logger.error(f"Simple mode PDF processing failed: {e}")
            return "这是一个占位符，用于保证边缘情况，需要图片处理走normal模式"

    async def process_pdf_normal(self, pdf_url: str) -> str:
        """标准模式：使用OCR服务处理PDF"""
        try:
            text = await self.ocr_provider.extract_markdown_from_pdf(pdf_url)

            if not text or text.strip() == "":
                text = "这是一个占位符，用于保证边缘情况，文档已经过OCR处理"
                logger.info(
                    "OCR processing returned empty result, using placeholder text"
                )

            logger.info(
                f"Normal mode PDF processing completed, {len(text)} characters extracted"
            )
            return text

        except Exception as e:
            logger.error(f"Normal mode PDF processing failed: {e}")
            return "这是一个占位符，用于保证边缘情况，文档已经过OCR处理"

    async def process_pdf_to_structured_content(
        self,
        pdf_url: str,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        mode: str = "simple",
    ) -> List[Dict[str, Any]]:
        """
        处理PDF到结构化内容

        Args:
            pdf_url: PDF文件URL
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            document_id: 文档ID
            mode: 处理模式 ("simple" 或 "normal")

        Returns:
            结构化内容列表
        """
        try:
            file_uuid = document_id
            pdf_url.split("/")[-1]
            local_file_path = self.tmp_dir / f"{file_uuid}.{pdf_url.split('.')[-1]}"

            logger.info("=== Stage 1: Download file ===")
            logger.info(
                f"Request: user_id={user_id}, file_url={pdf_url}, knowledge_base_id={knowledge_base_id}, mode={mode}"
            )

            # 下载文件到本地
            await self.downloader.download_file(pdf_url, str(local_file_path))
            logger.info(f"File downloaded successfully: {local_file_path}")

            logger.info("=== Stage 2: Extract text ===")

            # 根据模式处理PDF
            if mode == "simple":
                text = await self.process_pdf_simple(str(local_file_path))
            elif mode == "normal":
                text = await self.process_pdf_normal(pdf_url)
            else:
                raise ValueError(f"Invalid mode: {mode}")

            logger.info(f"Text extraction completed, {len(text)} characters")

            logger.info("=== Stage 3: Process content structure ===")

            # 处理文本内容结构
            structured_content = await self.text_processor.process_text_content(
                text, user_id, knowledge_base_id, document_id
            )

            logger.info(
                f"Content structure processing completed, {len(structured_content)} segments"
            )

            return structured_content

        except Exception as e:
            logger.error(f"PDF processing pipeline failed: {e}")
            raise
        finally:
            # 清理临时文件
            try:
                if local_file_path.exists():
                    await asyncio.to_thread(local_file_path.unlink, missing_ok=True)
                    logger.info(f"Temporary file deleted: {local_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temporary file: {cleanup_error}")

    async def get_pipeline_info(self) -> Dict[str, Any]:
        """获取流水线信息"""
        return {
            "ocr_provider": self.ocr_provider.get_provider_name(),
            "supported_modes": ["simple", "normal"],
            "temp_directory": str(self.tmp_dir),
            "config_loaded": bool(self.config),
        }
