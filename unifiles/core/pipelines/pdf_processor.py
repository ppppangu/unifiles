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
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from unifiles.core.logging import get_logger
from unifiles.core.ocr.factory import OCRProviderFactory
from unifiles.core.storage import get_initialized_storage

from ..config.env_config import convert_to_internal_minio_url, read_config

logger = get_logger()


# OCR接口定义
class OCRProvider(Protocol):
    """OCR提供者接口"""

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        ...


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
                    trust_env=False,  # 禁用系统代理，避免Windows代理设置导致502错误
                ) as client:
                    # 先尝试 HEAD 检查，失败继续 GET
                    try:
                        await client.head(target_url)
                    except Exception:
                        logger.debug("HEAD request failed, fallback to GET")

                    response = await client.get(target_url)
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
                        f"Download succeeded: {target_url} -> {file_path} ({len(response.content)} bytes)"
                    )
                    return file_path

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error {e.response.status_code} on {target_url}: {e.response.reason_phrase}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error on {target_url}: {e!s}")
                raise
            except Exception as e:
                logger.error(f"Download failed for {target_url}: {e!s}")
                raise Exception(f"Download failed: {e!s}")

        # 主下载逻辑
        try:
            return await _do_request(file_url)
        except Exception as first_error:
            # 如果失败且符合公网前缀，尝试内网URL
            internal_url = convert_to_internal_minio_url(original_url)
            if internal_url != original_url:
                logger.warning(
                    f"Primary download failed, retrying internal URL: {internal_url}"
                )
                try:
                    return await _do_request(internal_url)
                except Exception as second_error:
                    logger.error("Internal URL fallback download failed")
                    raise second_error from first_error
            raise


class TextProcessor:
    """文本处理器 - 负责分块和分层处理"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        # 记录最近一次在分块之前的完整Markdown（已转换图片路径）
        self._last_full_markdown: Optional[str] = None

    def get_last_full_markdown(self) -> Optional[str]:
        """获取最近一次处理时的未分块完整Markdown（图片路径已转换）。"""
        return self._last_full_markdown

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

    def _convert_image_paths(
        self, text: str, user_id: str, knowledge_base_id: str, document_id: str
    ) -> str:
        """将markdown中的相对图片路径转换为对象路径，返回转换后的完整文本。

        注：已删除分块逻辑，该方法不再返回分段，仅做路径转换。
        """
        if not text:
            return ""

        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        converted_parts: List[str] = []

        last_pos = 0
        for m in re.finditer(pattern, text):
            start, end = m.start(), m.end()
            # 追加前置文本
            if last_pos < start:
                pre = text[last_pos:start]
                if pre:
                    converted_parts.append(pre)

            # 图片片段（路径转换为对象路径）
            alt_text = m.group(1)
            image_path = m.group(2)
            object_path = f"{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path}"
            converted = f"![{alt_text}]({object_path})"
            converted_parts.append(converted)

            last_pos = end

        # 末尾文本
        if last_pos < len(text):
            tail = text[last_pos:]
            if tail:
                converted_parts.append(tail)

        converted_text = "".join(converted_parts)
        return converted_text

    async def process_text_content(
        self,
        text: str,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
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
            converted_text = await asyncio.to_thread(
                self._convert_image_paths, text, user_id, knowledge_base_id, document_id
            )
            # 保存未分块的完整Markdown，以供上层用于 full_markdown 持久化
            self._last_full_markdown = converted_text

            # 步骤2：不进行任何分块，返回单一整段内容（包含已转换好的图片路径）
            final_segments: List[Dict[str, Any]] = [
                {
                    "content": converted_text,
                    "index": 0,
                    "type": "text",
                    "embedding": None,
                }
            ]

            logger.info(
                "Text processed",
                {
                    "text_length": len(text),
                    "segments": len(final_segments),
                },
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
        self.default_provider_name = (
            ocr_provider.get_provider_name() if ocr_provider else "simple"
        )  # 默认使用simple provider
        self.downloader = FileDownloader(config)
        self.text_processor = TextProcessor(config)
        # 缓存最近一次处理得到的未分块完整Markdown
        self._last_full_markdown: Optional[str] = None

        # 创建临时目录
        self.tmp_dir = Path(__file__).parent / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

    def set_ocr_provider(self, provider: OCRProvider):
        """设置OCR提供者（支持运行时替换）。仅记录 provider 名称以兼容旧调用。"""
        self.default_provider_name = provider.get_provider_name()
        logger.info(f"OCR provider changed to: {self.default_provider_name}")

    async def process_pdf_to_structured_content(
        self,
        pdf_url: str,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        mode: str = "simple",
        parse_image_content: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        处理PDF到结构化内容

        Args:
            pdf_url: PDF文件URL
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            document_id: 文档ID
            mode: 处理模式 ("simple" 或 特定的OCR提供商名称)
            parse_image_content: 是否解析图像内容到full_markdown

        Returns:
            结构化内容列表
        """
        try:
            file_uuid = document_id
            local_file_path = self.tmp_dir / f"{file_uuid}.{pdf_url.split('.')[-1]}"

            logger.info(
                "PDF pipeline started",
                {
                    "user_id": user_id,
                    "kb_id": knowledge_base_id,
                    "doc_id": document_id,
                    "mode": mode,
                },
            )

            # 下载文件到本地
            await self.downloader.download_file(pdf_url, str(local_file_path))
            logger.info(f"File downloaded: {local_file_path}")

            # 根据模式处理PDF（统一走 OCRProviderFactory）
            provider_name = mode or self.default_provider_name or "simple"
            supported_providers = OCRProviderFactory.get_supported_providers()
            if provider_name not in supported_providers:
                logger.warning(
                    f"OCR provider '{provider_name}' not supported, falling back to Mistral"
                )
                provider_name = "mistral"

            logger.info(f"Using OCR provider: {provider_name}")
            images_info = []
            try:
                provider = OCRProviderFactory.create_provider(provider_name)
            except Exception as create_err:
                logger.error(
                    f"Failed to create OCR provider {provider_name}: {create_err}"
                )
                raise

            if provider_name == "selfhosted" and parse_image_content:
                text, images_info = await provider.aprocess_file(
                    str(local_file_path),
                    parse_image_content=parse_image_content,
                )
            else:
                text, images_info = await provider.aprocess_file(str(local_file_path))

            if not text or text.strip() == "":
                text = "这是一个占位符，用于保证边缘情况，文档已经过OCR处理"
                logger.info(
                    f"{provider_name} OCR processing returned empty result, using placeholder text"
                )

            logger.info(
                f"Text extraction completed: {len(text)} chars, {len(images_info)} images"
            )

            # 避免将包含 bytes 的大对象写入日志，只输出精简统计信息
            try:
                total_img_bytes = sum(
                    int(img.get("size_bytes", 0)) for img in images_info
                )
                sample_names = [img.get("filename") for img in images_info[:3]]
                logger.debug(
                    "Extracted images summary: count=%d, total_bytes=%d, samples=%s",
                    len(images_info),
                    total_img_bytes,
                    sample_names,
                )
            except Exception:
                # 兜底：即便统计失败，也不要打印原始 images_info 以免日志过大
                logger.debug(f"Extracted images summary: count={len(images_info)}")

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

            # 记录未分块完整Markdown（优先从 TextProcessor 获取）
            try:
                self._last_full_markdown = (
                    self.text_processor.get_last_full_markdown() or text
                )
            except Exception:
                self._last_full_markdown = text

            # 在 structured_content 中添加图片元数据信息
            if images_info:
                # 将图片信息添加到返回的元数据中
                for content_item in structured_content:
                    if "metadata" not in content_item:
                        content_item["metadata"] = {}
                    content_item["metadata"]["extracted_images_count"] = len(
                        images_info
                    )

                logger.debug(
                    f"Added extracted image metadata: {len(images_info)} items"
                )

            logger.info(
                f"Content structuring completed: {len(structured_content)} segments"
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
                    logger.debug(f"Temporary file deleted: {local_file_path}")
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
            "ocr_provider": self.default_provider_name,
            "supported_modes": providers,
            "temp_directory": str(self.tmp_dir),
            "config_loaded": bool(self.config),
        }

    def get_last_full_markdown(self) -> Optional[str]:
        """返回最近一次处理时的未分块完整Markdown。

        用途：用于数据库 full_markdown 字段持久化，避免因分块（特别是重叠窗口）
        导致重复或与原始内容不一致的问题。
        """
        return self._last_full_markdown
