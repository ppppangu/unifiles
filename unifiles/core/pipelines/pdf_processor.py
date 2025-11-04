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
import fitz  # PyMuPDF
import httpx
import pdfplumber
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from unifiles.core.logging import get_logger
from unifiles.core.ocr.factory import OCRProviderFactory
from unifiles.core.ocr.processor import OCRProcessor
from unifiles.core.storage import get_initialized_storage

from ..config.env_config import convert_to_internal_minio_url, read_config

logger = get_logger()


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


class GenericOCRAdapter:
    """通用OCR适配器：按名称实例化ocr模块中的Provider并适配到本流水线接口。"""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        """根据名称初始化OCR供应商"""
        try:
            self.provider = OCRProviderFactory.create_provider(self.provider_name)
            logger.info(
                f"Initialized OCR provider: {self.provider.get_provider_name()}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize OCR provider {self.provider_name}: {e}")
            raise

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        if self.provider:
            return self.provider.get_provider_name()
        return self.provider_name

    async def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取文本"""
        if not self.provider:
            logger.error("No OCR provider initialized")
            return ""

        try:
            return await self.provider.extract_text_from_pdf(pdf_path_or_url)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取Markdown格式文本"""
        if not self.provider:
            logger.error("No OCR provider initialized")
            return ""

        try:
            return await self.provider.extract_markdown_from_pdf(pdf_path_or_url)
        except Exception as e:
            logger.error(f"Error extracting markdown from PDF: {e}")
            return ""


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

    async def extract_text_by_page(self, pdf_path: str) -> List[str]:
        """按页提取PDF文本，返回每页的文本列表

        Args:
            pdf_path: PDF文件路径

        Returns:
            List[str]: 每页的文本内容列表
        """
        try:
            # 获取页数
            page_count = await asyncio.to_thread(self._get_pdf_page_count, pdf_path)
            if page_count == 0:
                return []

            # 并行读取所有页面
            tasks = [
                asyncio.to_thread(self._read_pdf_page, pdf_path, page_num)
                for page_num in range(page_count)
            ]
            results = await asyncio.gather(*tasks)

            logger.info(f"Extracted text from {page_count} pages")
            return list(results)

        except Exception as e:
            logger.error(f"Error extracting text by page from PDF: {e}")
            return []

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取Markdown（简单实现）"""
        text = await self.extract_text_from_pdf(pdf_path_or_url)
        # 简单的文本到Markdown转换
        if text:
            return f"# PDF Content\n\n{text}"
        return ""

    def _extract_images_from_page(
        self, file_path: str, page_num: int
    ) -> List[Dict[str, Any]]:
        """从PDF指定页提取图片（优化：不保存到磁盘，直接使用字节数据）

        Args:
            file_path: PDF文件路径
            page_num: 页码（从0开始）

        Returns:
            图片信息列表，包含字节数据、文件名、页码、索引等元数据
        """
        images_info = []

        try:
            # 使用 PyMuPDF 提取图片
            doc = fitz.open(file_path)
            if page_num >= len(doc):
                return images_info

            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]  # ← 已经是字节数据！
                    image_ext = base_image["ext"]  # png, jpeg, etc

                    # 构建图片文件名
                    image_filename = (
                        f"page_{page_num:03d}_img_{img_index:03d}.{image_ext}"
                    )

                    # === 优化：直接收集字节数据，不保存文件 ===
                    images_info.append(
                        {
                            "page": page_num,
                            "index": img_index,
                            "filename": image_filename,
                            "bytes": image_bytes,  # ← 直接使用字节数据
                            "extension": image_ext,
                            "size_bytes": len(image_bytes),
                        }
                    )

                    logger.debug(
                        f"Extracted image: page {page_num}, index {img_index}, size {len(image_bytes)} bytes"
                    )

                except Exception as e:
                    logger.error(
                        f"Error extracting image {img_index} from page {page_num}: {e}"
                    )
                    continue

            doc.close()

        except Exception as e:
            logger.error(f"Error extracting images from page {page_num}: {e}")

        return images_info

    async def extract_images_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """从PDF提取所有图片（优化：不保存到磁盘，直接返回字节数据）

        Args:
            pdf_path: PDF文件路径

        Returns:
            所有图片的信息列表，包含字节数据
        """
        try:
            # 获取页数
            page_count = await asyncio.to_thread(self._get_pdf_page_count, pdf_path)
            if page_count == 0:
                return []

            # 并行提取所有页面的图片（无需创建目录）
            tasks = [
                asyncio.to_thread(self._extract_images_from_page, pdf_path, page_num)
                for page_num in range(page_count)
            ]
            results = await asyncio.gather(*tasks)

            # 合并所有页面的图片信息
            all_images = []
            for page_images in results:
                all_images.extend(page_images)

            logger.info(
                f"Extracted {len(all_images)} images from {page_count} pages (memory only, no disk I/O)"
            )

            return all_images

        except Exception as e:
            logger.error(f"Error extracting images from PDF: {e}")
            return []


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
            logger.info(match.group(0))
            logger.info(f"Found image: match at {match.start()}-{match.end()}")
            image_matches.append((match.start(), match.end(), "image"))

        # 按开始位置排序
        logger.info(image_matches)
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

        logger.info(results)

        # 处理剩余文本
        if image_matches:
            if current_pos < text_length:
                results.append((current_pos, text_length, "text"))
        # 如果没有找到任何图片，整个文本都是文本片段
        elif text_length > 0:
            results.append((0, text_length, "text"))

        # 按开始位置排序结果
        results.sort(key=lambda x: x[0])

        # 构建转换后的文本：将相对图片路径转换为仅包含对象路径（不包含域名/桶前缀）
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

                    logger.info(f"alt text: {alt_text}, image_path: {image_path}")

                    # 将相对路径转换为对象路径（仅对象键，不包含协议/域名/桶）
                    # 与上传阶段保持一致：{user_id}/knowledge_base/{kb}/{doc}/{filename}
                    object_path = f"{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path}"

                    converted_markdown = f"![{alt_text}]({object_path})"
                    converted_text += converted_markdown
                else:
                    converted_text += image_markdown
        logger.info(converted_text)
        logger.info(results)
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

        logger.info(f"Converted text: {converted_text}")

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

    def _segment_by_images(
        self, text: str, user_id: str, knowledge_base_id: str, document_id: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """按图片边界切分文本，并在过程中将图片相对路径转换为对象路径。

        Returns:
            tuple: (converted_text, segments)
                - converted_text: 路径转换后的完整文本
                - segments: 切分后的片段列表，每个元素包含：{"content": str, "type": "text"|"image"}

        注意：segments中的content已经是转换后的内容，与converted_text保持一致
        """
        if not text:
            return "", []

        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        segments: List[Dict[str, Any]] = []
        converted_parts: List[str] = []

        last_pos = 0
        for m in re.finditer(pattern, text):
            start, end = m.start(), m.end()
            # 追加前置文本
            if last_pos < start:
                pre = text[last_pos:start]
                if pre.strip():
                    segments.append({"content": pre, "type": "text"})
                    converted_parts.append(pre)
                elif pre:  # 保留空白字符
                    converted_parts.append(pre)

            # 图片片段（路径转换为对象路径）
            alt_text = m.group(1)
            image_path = m.group(2)
            object_path = f"{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path}"
            converted = f"![{alt_text}]({object_path})"
            segments.append({"content": converted, "type": "image"})
            converted_parts.append(converted)

            last_pos = end

        # 末尾文本
        if last_pos < len(text):
            tail = text[last_pos:]
            if tail.strip():
                segments.append({"content": tail, "type": "text"})
                converted_parts.append(tail)
            elif tail:  # 保留空白字符
                converted_parts.append(tail)

        converted_text = "".join(converted_parts)
        return converted_text, segments

    async def process_text_content(
        self, text: str, user_id: str, knowledge_base_id: str, document_id: str
    ) -> List[Dict[str, Any]]:
        """
        处理文本内容：
        - 步骤1：按图片边界切分（并将图片链接转换为对象路径）
        - 步骤2：仅对文本片段进行分块

        Returns:
            处理后的内容列表，每个元素包含content、index、type、embedding字段

        注意：返回的content中，图片路径已经转换为对象路径格式
        """
        try:
            # 步骤1：按图片边界切分，同时获取转换后的完整文本
            logger.info("Processing text content - Step 1: Segment by image boundaries")
            converted_text, base_segments = await asyncio.to_thread(
                self._segment_by_images, text, user_id, knowledge_base_id, document_id
            )
            logger.info(
                "Image segmentation completed",
                {
                    "segments": len(base_segments),
                    "text_length_before": len(text),
                    "text_length_after": len(converted_text),
                },
            )

            # 步骤2：对文本类型进行分块
            logger.info("Processing text content - Step 2: Text chunking")
            final_segments: List[Dict[str, Any]] = []
            for seg in base_segments:
                if seg["type"] == "text":
                    chunks = await self.split_text(seg["content"])
                    for chunk in chunks:
                        final_segments.append(
                            {
                                "content": chunk,
                                "index": len(final_segments),
                                "type": "text",
                                "embedding": None,
                            }
                        )
                else:
                    # 图片片段不分块，直接添加
                    final_segments.append(
                        {
                            "content": seg["content"],
                            "index": len(final_segments),
                            "type": seg["type"],
                            "embedding": None,
                        }
                    )

            logger.info(
                "Text chunking completed",
                {"segments": len(final_segments)},
            )
            return final_segments

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

    async def process_pdf_simple(
        self, pdf_path: str, extract_images: bool = True
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """简单模式：使用pdfplumber读取PDF

        Args:
            pdf_path: PDF文件路径
            extract_images: 是否提取图片，默认为True

        Returns:
            Tuple[str, List[Dict]]: (markdown文本, 图片信息列表)
        """
        try:
            simple_reader = SimplePDFReader()

            # 提取图片（优化：不创建目录，直接获取字节数据）
            images_info = []
            images_by_page: Dict[int, List[Dict[str, Any]]] = {}

            if extract_images:
                # === 优化：不再创建目录，直接提取 ===
                images_info = await simple_reader.extract_images_from_pdf(pdf_path)

                # 按页码分组图片
                for img_info in images_info:
                    page_num = img_info["page"]
                    if page_num not in images_by_page:
                        images_by_page[page_num] = []
                    images_by_page[page_num].append(img_info)

            # 按页提取文本
            page_texts = await simple_reader.extract_text_by_page(pdf_path)

            if not page_texts or all(not t.strip() for t in page_texts):
                # 如果所有页都没有文本，使用占位符
                logger.info(
                    "PDF appears to be image-based or empty, using placeholder text"
                )
                return (
                    "# PDF Content\n\n这是一个占位符，用于保证边缘情况，需要图片处理请使用OCR提供商模式",
                    images_info,
                )

            # 构建Markdown：每页文本后面紧跟该页的图片引用
            markdown_parts = []

            for page_num, page_text in enumerate(page_texts):
                # 添加页面文本
                if page_text and page_text.strip():
                    markdown_parts.append(f"{page_text}\n\n")

                # 添加该页的图片引用（紧跟在文本后面）
                if page_num in images_by_page:
                    for img_info in images_by_page[page_num]:
                        markdown_parts.append(
                            f"![{img_info['filename']}]({img_info['filename']})\n\n"
                        )

            text = "".join(markdown_parts)

            logger.info(
                f"Simple mode PDF processing completed: {len(text)} characters, {len(images_info)} images extracted"
            )
            return text, images_info

        except Exception as e:
            logger.error(f"Simple mode PDF processing failed: {e}")
            return (
                "这是一个占位符，用于保证边缘情况，需要图片处理请使用OCR提供商模式",
                [],
            )

    async def process_pdf_with_ocr_provider(
        self, pdf_path: str, provider_name: str
    ) -> Tuple[str, List[Dict]]:
        """使用指定的OCR提供商处理PDF文件

        Args:
            pdf_path: PDF文件路径
            provider_name: OCR提供商名称

        Returns:
            Tuple[str, List[Dict]]: (markdown文本, 图片信息列表)
        """
        try:
            # 检查提供商是否受支持
            if provider_name not in OCRProviderFactory.get_supported_providers():
                logger.warning(
                    f"OCR provider '{provider_name}' not supported, falling back to Mistral"
                )
                provider_name = "mistral"

            # 创建OCR处理器
            ocr_processor = OCRProcessor(provider_name)

            # 使用OCR提取文本（优化后不再需要 output_dir，图片数据直接在内存中）
            logger.info(f"Processing PDF with {provider_name} OCR provider")
            text, images_info = await ocr_processor.aprocess_file(pdf_path)

            if not text or text.strip() == "":
                text = "这是一个占位符，用于保证边缘情况，文档已经过OCR处理"
                logger.info(
                    f"{provider_name} OCR processing returned empty result, using placeholder text"
                )

            logger.info(
                f"{provider_name} OCR PDF processing completed, {len(text)} characters extracted"
            )
            return text, images_info
        except Exception as e:
            logger.error(f"{provider_name} OCR PDF processing failed: {e}")
            return "这是一个占位符，用于保证边缘情况，文档已经过OCR处理", []

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
            mode: 处理模式 ("simple" 或 特定的OCR提供商名称)

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
            images_info = []
            if mode == "simple":
                text, images_info = await self.process_pdf_simple(str(local_file_path))
            else:
                # 模式直接作为OCR提供商名称处理
                logger.info(f"Using OCR provider: {mode}")
                text, images_info = await self.process_pdf_with_ocr_provider(
                    str(local_file_path), mode
                )

            logger.info(
                f"Text extraction completed, {len(text)} characters, {len(images_info)} images"
            )

            # 避免将包含 bytes 的大对象写入日志，只输出精简统计信息
            try:
                total_img_bytes = sum(
                    int(img.get("size_bytes", 0)) for img in images_info
                )
                sample_names = [img.get("filename") for img in images_info[:3]]
                logger.info(
                    "Extracted images summary: count=%d, total_bytes=%d, samples=%s",
                    len(images_info),
                    total_img_bytes,
                    sample_names,
                )
            except Exception:
                # 兜底：即便统计失败，也不要打印原始 images_info 以免日志过大
                logger.info(f"Extracted images summary: count={len(images_info)}")

            # === Stage 2.5: Upload extracted images to storage (MinIO) ===
            # Note: OCR providers can return images as bytes (memory) or path (file).
            # Priority: bytes (no disk I/O) > path (fallback for simple mode).
            if images_info:
                try:
                    storage = await get_initialized_storage()
                    backend = await storage.get_default_backend()

                    # Helper to guess MIME type from file extension
                    def _mime_from_ext(ext: str) -> str:
                        ext = (ext or "").lower().lstrip(".")
                        if ext in {"jpg", "jpeg"}:
                            return "image/jpeg"
                        if ext in {"png"}:
                            return "image/png"
                        return "application/octet-stream"

                    for img in images_info:
                        filename = img.get("filename")
                        object_path = f"{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{filename}"

                        img_bytes = img.get("bytes")
                        local_path = img.get("path")
                        content_type = _mime_from_ext(img.get("extension"))

                        try:
                            if img_bytes:
                                # === 新路径：从内存上传（OCR providers） ===
                                await backend.upload_file(
                                    object_path=object_path,
                                    content=img_bytes,
                                    content_type=content_type,
                                )
                                logger.debug(
                                    f"Uploaded from memory: {filename} ({len(img_bytes)} bytes)"
                                )
                            elif local_path:
                                # === 旧路径：从文件上传（simple mode 兼容） ===
                                await backend.upload_file_from_path(
                                    object_path=object_path,
                                    local_file_path=local_path,
                                    content_type=content_type,
                                )
                                logger.debug(f"Uploaded from file: {filename}")
                            else:
                                logger.warning(
                                    f"Image {filename} has no bytes or path, skipping upload"
                                )
                                continue

                            public_url = backend.get_access_url(
                                object_path, access_type="public"
                            )

                            # Enrich images_info with storage references
                            img["object_path"] = object_path
                            img["public_url"] = public_url

                            # Release memory for bytes data
                            if "bytes" in img:
                                del img["bytes"]

                            logger.debug(f"Image uploaded successfully: {object_path}")
                        except Exception as upload_err:
                            logger.warning(
                                f"Failed to upload image '{filename}': {upload_err}"
                            )
                except Exception as storage_err:
                    logger.warning(
                        f"Image upload stage skipped due to storage error: {storage_err}"
                    )

            logger.info("=== Stage 3: Process content structure ===")

            # 处理文本内容结构进行分块
            structured_content = await self.text_processor.process_text_content(
                text, user_id, knowledge_base_id, document_id
            )

            # 在 structured_content 中添加图片元数据信息
            if images_info:
                # 将图片信息添加到返回的元数据中
                for content_item in structured_content:
                    if "metadata" not in content_item:
                        content_item["metadata"] = {}
                    content_item["metadata"]["extracted_images_count"] = len(
                        images_info
                    )

                # 可选：将图片信息作为额外的元数据返回
                logger.info(
                    f"Added {len(images_info)} images metadata to structured content"
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
        try:
            from ..ocr.factory import OCRProviderFactory

            providers = OCRProviderFactory.get_supported_providers()
        except Exception:
            providers = []

        return {
            "ocr_provider": self.ocr_provider.get_provider_name(),
            "supported_modes": ["simple"].append(providers),
            "temp_directory": str(self.tmp_dir),
            "config_loaded": bool(self.config),
        }
