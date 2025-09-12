"""
文档处理服务
整合所有流水线组件，提供完整的文档处理功能
这是基于app/legacy/main.py中mineru_process函数的重构版本
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..pipelines.format_validator import FormatValidationPipeline
from ..pipelines.pdf_processor import (
    MineruOCRProvider,
    PDFProcessingPipeline,
    SimplePDFReader,
)
from ..services.embedding_service import EmbeddingService
from ..services.storage_service import StorageService
from ..utils.tools import read_config


class DocumentProcessingService:
    """文档处理服务主类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()

        # 初始化各个组件
        self.format_pipeline = FormatValidationPipeline(config)
        self.pdf_pipeline = PDFProcessingPipeline(config=config)
        self.embedding_service = EmbeddingService(config=config)
        self.storage_service = StorageService(config=config)

        # 创建临时目录
        self.tmp_dir = Path(__file__).parent / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

    def set_ocr_provider(self, provider_type: str = "simple"):
        """设置OCR提供者"""
        if provider_type == "simple":
            self.pdf_pipeline.set_ocr_provider(SimplePDFReader())
        elif provider_type == "mineru":
            self.pdf_pipeline.set_ocr_provider(MineruOCRProvider(self.config))
        else:
            raise ValueError(f"Unknown OCR provider type: {provider_type}")

        logger.info(f"OCR provider set to: {provider_type}")

    async def process_file_from_upload(
        self,
        filename: str,
        file_content: bytes,
        user_id: str,
        knowledge_base_id: str = None,
        mode: str = "simple",
    ) -> Dict[str, Any]:
        """
        处理上传的文件

        Args:
            filename: 文件名
            file_content: 文件内容
            user_id: 用户ID
            knowledge_base_id: 知识库ID，None时使用默认值
            mode: 处理模式 ("simple" 或 "normal")

        Returns:
            处理结果字典
        """
        try:
            # 设置默认知识库ID
            if not knowledge_base_id:
                knowledge_base_id = f"df_{user_id}"

            document_id = str(uuid.uuid4())

            logger.info(f"=== Starting file processing ===")
            logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            logger.info(f"File: {filename}, Size: {len(file_content)} bytes")

            # 第一步：格式验证和PDF转换
            logger.info(f"=== Stage 1: Format validation and PDF conversion ===")

            # 创建临时文件URL（实际应用中这应该是真实的文件URL）
            temp_file_path = self.tmp_dir / f"{document_id}_{filename}"
            async with aiofiles.open(temp_file_path, "wb") as f:
                await f.write(file_content)

            # 生成临时URL（在实际应用中，这应该是已上传文件的URL）
            file_url = f"file://{temp_file_path.absolute()}"

            # 格式验证和PDF转换
            validation_result = await self.format_pipeline.process_file(
                filename, file_content, file_url
            )

            if not validation_result["success"]:
                return {
                    "success": False,
                    "error": "Format validation failed",
                    "details": validation_result["errors"],
                }

            pdf_url = validation_result["pdf_url"]
            logger.info(f"PDF ready for processing: {pdf_url}")

            # 设置OCR提供者
            if mode == "simple":
                self.set_ocr_provider("simple")
            elif mode == "normal":
                self.set_ocr_provider("mineru")

            # 第二步：PDF处理和内容提取
            logger.info(f"=== Stage 2: PDF processing and content extraction ===")

            structured_content = (
                await self.pdf_pipeline.process_pdf_to_structured_content(
                    pdf_url=pdf_url,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    mode=mode,
                )
            )

            logger.info(
                f"Content extraction completed: {len(structured_content)} segments"
            )

            # 第三步：嵌入处理
            logger.info(f"=== Stage 3: Embedding processing ===")

            embedded_content = await self.embedding_service.embed_content_batch(
                structured_content
            )
            logger.info(
                f"Embedding processing completed for {len(embedded_content)} segments"
            )

            # 第四步：存储处理结果
            logger.info(f"=== Stage 4: Storage processing ===")

            # 重新构建markdown内容
            markdown_content = ""
            for item in embedded_content:
                markdown_content += item["content"] + "\n\n"

            # 保存处理结果
            storage_result = await self.storage_service.save_processing_results(
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                document_name=filename,
                markdown_content=markdown_content,
                pdf_file_path=str(temp_file_path),  # 在实际应用中这应该是PDF文件路径
                structured_content=embedded_content,
            )

            # 清理临时文件
            await self.storage_service.cleanup_temporary_files(str(temp_file_path))

            # 构建成功响应
            result = {
                "success": True,
                "data": {
                    "user_id": user_id,
                    "knowledge_base_id": knowledge_base_id,
                    "mode": mode,
                    "file_url": pdf_url,  # 返回处理后的PDF URL
                    "markdown_public_url": storage_result["markdown_public_url"],
                    "pdf_file_public_url": storage_result["pdf_file_public_url"],
                    "file_uuid": storage_result["file_uuid"],
                    "component_count": storage_result["component_count"],
                },
            }

            logger.info(f"=== File processing completed successfully ===")
            logger.info(
                f"Document ID: {document_id}, Components: {storage_result['component_count']}"
            )

            return result

        except Exception as e:
            logger.error(f"File processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "details": {"exception_type": type(e).__name__},
            }

    async def process_file_from_url(
        self,
        file_url: str,
        user_id: str,
        knowledge_base_id: str = None,
        mode: str = "simple",
        raw_file_url_to_return: str = None,
    ) -> Dict[str, Any]:
        """
        处理来自URL的文件（重构版的mineru_process函数）

        Args:
            file_url: 文件URL
            user_id: 用户ID
            knowledge_base_id: 知识库ID，None时使用默认值
            mode: 处理模式 ("simple" 或 "normal")
            raw_file_url_to_return: 要返回的原始文件URL

        Returns:
            处理结果字典，格式兼容原始mineru_process函数
        """
        try:
            # 设置默认值
            if not knowledge_base_id:
                knowledge_base_id = f"df_{user_id}"

            if not raw_file_url_to_return:
                raw_file_url_to_return = file_url

            document_id = str(uuid.uuid4())
            filename = file_url.split("/")[-1] if "/" in file_url else "document.pdf"

            logger.info(f"=== Starting URL file processing ===")
            logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            logger.info(f"File URL: {file_url}")

            # 第一步：格式验证和PDF转换
            logger.info(f"=== Stage 1: Format validation and PDF conversion ===")

            validation_result = await self.format_pipeline.process_file_url_only(
                file_url
            )

            if not validation_result["success"]:
                logger.error(f"Format validation failed: {validation_result['errors']}")
                return None

            pdf_url = validation_result["pdf_url"]
            logger.info(f"PDF ready for processing: {pdf_url}")

            # 设置OCR提供者
            if mode == "simple":
                self.set_ocr_provider("simple")
            elif mode == "normal":
                self.set_ocr_provider("mineru")

            # 第二步：PDF处理和内容提取
            logger.info(f"=== Stage 2: PDF processing and content extraction ===")

            structured_content = (
                await self.pdf_pipeline.process_pdf_to_structured_content(
                    pdf_url=pdf_url,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    mode=mode,
                )
            )

            logger.info(
                f"Content extraction completed: {len(structured_content)} segments"
            )

            # 第三步：嵌入处理
            logger.info(f"=== Stage 3: Embedding processing ===")

            embedded_content = await self.embedding_service.embed_content_batch(
                structured_content
            )
            logger.info(
                f"Embedding processing completed for {len(embedded_content)} segments"
            )

            # 第四步：存储到向量数据库
            logger.info(f"=== Stage 4: Vector database storage ===")

            component_ids = (
                await self.storage_service.store_structured_content_to_vector_db(
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    document_name=filename,
                    structured_content=embedded_content,
                )
            )

            logger.info(
                f"Vector database storage completed: {len(component_ids)} components stored"
            )

            # 第五步：云端存储处理结果
            logger.info(f"=== Stage 5: Cloud storage ===")

            # 重新构建markdown内容
            markdown_content = ""
            for item in embedded_content:
                markdown_content += item["content"] + "\n\n"

            # 创建临时文件用于上传
            temp_md_file = self.tmp_dir / f"{document_id}.md"
            temp_pdf_file = self.tmp_dir / f"{document_id}.pdf"

            # 保存markdown文件
            async with aiofiles.open(temp_md_file, "w", encoding="utf-8") as f:
                await f.write(markdown_content)

            # 下载PDF文件到本地（为了上传）
            from ..pipelines.pdf_processor import FileDownloader

            downloader = FileDownloader(self.config)
            await downloader.download_file(pdf_url, str(temp_pdf_file))

            # 存储处理后的文件
            file_urls = await self.storage_service.store_processed_files(
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                markdown_content=markdown_content,
                pdf_file_path=str(temp_pdf_file),
                original_filename=filename,
            )

            # 更新文档URL（包含原始文件URL）
            await self.storage_service.db_manager.update_document_urls(
                document_id, file_urls["markdown_public_url"], raw_file_url_to_return
            )

            # 清理临时文件
            await self.storage_service.cleanup_temporary_files(
                str(temp_md_file), str(temp_pdf_file)
            )

            # 返回兼容原始函数格式的结果
            result = {
                "markdown_public_url": file_urls["markdown_public_url"],
                "pdf_file_public_url": file_urls["pdf_file_public_url"],
                "file_uuid": document_id,
            }

            logger.info(f"=== URL file processing completed successfully ===")
            logger.info(f"Document ID: {document_id}, Components: {len(component_ids)}")
            logger.info(f"Markdown URL: {file_urls['markdown_public_url']}")
            logger.info(f"PDF URL: {file_urls['pdf_file_public_url']}")

            return result

        except Exception as e:
            logger.error(f"URL file processing failed: {str(e)}")
            return None

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": "DocumentProcessingService",
            "version": "1.0.0",
            "supported_modes": ["simple", "normal"],
            "format_pipeline": self.format_pipeline.validator.SUPPORTED_FILE_TYPES,
            "pdf_pipeline": self.pdf_pipeline.get_pipeline_info(),
            "embedding_service": self.embedding_service.get_service_info(),
            "storage_service": self.storage_service.get_service_info(),
            "temp_directory": str(self.tmp_dir),
        }


# 默认文档处理服务实例
_default_document_processor: Optional[DocumentProcessingService] = None


def get_document_processor(
    config: Optional[Dict[str, Any]] = None,
) -> DocumentProcessingService:
    """获取默认文档处理服务实例（单例模式）"""
    global _default_document_processor
    if _default_document_processor is None:
        _default_document_processor = DocumentProcessingService(config=config)
    return _default_document_processor


# 为了保持向后兼容，提供原始函数接口
async def mineru_process(
    file_url: str,
    knowledge_base_id: str,
    mode: str,
    user_id: str,
    raw_file_url_to_return: str = "",
) -> Optional[Dict[str, str]]:
    """
    兼容原始mineru_process函数的接口
    这是对legacy/main.py中mineru_process函数的重构版本
    """
    processor = get_document_processor()
    return await processor.process_file_from_url(
        file_url=file_url,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        mode=mode,
        raw_file_url_to_return=raw_file_url_to_return,
    )
