"""
文档处理服务
整合所有流水线组件，提供完整的文档处理功能
这是基于app/legacy/main.py中mineru_process函数的重构版本
"""

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles

from ..config.env_config import read_config
from ..database import extraction_db_manager, unified_file_db_manager
from ..logging import get_logger
from ..pipelines.format_validator import FormatValidationPipeline
from ..pipelines.pdf_processor import PDFProcessingPipeline
from ..services.embedding_service import EmbeddingService
from ..services.storage_service import StorageService
from ..ocr.factory import OCRProviderFactory


def parse_image_assets_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """从markdown中解析图片信息

    Args:
        markdown: Markdown文本内容

    Returns:
        图片资源列表，每个元素包含：
        - index: 图片在文档中的序号
        - alt_text: 图片替代文本
        - object_path: 对象存储路径
        - filename: 文件名
    """
    pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
    assets = []

    for idx, match in enumerate(re.finditer(pattern, markdown)):
        alt_text = match.group(1)
        object_path = match.group(2)

        # 从对象路径中提取文件名
        filename = object_path.split("/")[-1] if "/" in object_path else object_path

        assets.append(
            {
                "index": idx,
                "alt_text": alt_text,
                "object_path": object_path,
                "filename": filename,
            }
        )

    return assets


class DocumentProcessingService:
    """文档处理服务主类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()

        # 获取统一的日志实例
        self.logger = get_logger()

        # 初始化各个组件
        self.format_pipeline = FormatValidationPipeline(config)
        self.pdf_pipeline = PDFProcessingPipeline(config=config)
        self.embedding_service = EmbeddingService(config=config)
        self.storage_service = StorageService(config=config)

        # 创建临时目录
        self.tmp_dir = Path(__file__).parent / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

    async def process_file_from_upload(
        self,
        filename: str,
        file_content: bytes,
        user_id: str,
        knowledge_base_id: Optional[str] = None,
        mode: str = "simple",
    ) -> Dict[str, Any]:
        """
        处理上传的文件

        Args:
            filename: 文件名
            file_content: 文件内容
            user_id: 用户ID
            knowledge_base_id: 知识库ID，None时使用默认值
            mode: 处理模式 ("simple" 或 特定的OCR提供商名称)

        Returns:
            处理结果字典
        """
        try:
            # 设置默认知识库ID
            if not knowledge_base_id:
                knowledge_base_id = f"df_{user_id}"

            document_id = str(uuid.uuid4())

            self.logger.info("=== Starting file processing ===")
            self.logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            self.logger.info(f"File: {filename}, Size: {len(file_content)} bytes")

            # 第一步：格式验证和PDF转换
            self.logger.info("=== Stage 1: Format validation and PDF conversion ===")

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
            self.logger.info(f"PDF ready for processing: {pdf_url}")

            # 第二步：PDF处理和内容提取
            self.logger.info("=== Stage 2: PDF processing and content extraction ===")

            structured_content = (
                await self.pdf_pipeline.process_pdf_to_structured_content(
                    pdf_url=pdf_url,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    mode=mode,
                )
            )

            self.logger.info(
                f"Content extraction completed: {len(structured_content)} segments"
            )

            # 第三步：嵌入处理
            self.logger.info("=== Stage 3: Embedding processing ===")

            embedded_content = await self.embedding_service.embed_content_batch(
                structured_content
            )
            self.logger.info(
                f"Embedding processing completed for {len(embedded_content)} segments"
            )

            # 第四步：存储处理结果
            self.logger.info("=== Stage 4: Storage processing ===")

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

            self.logger.info("=== File processing completed successfully ===")
            self.logger.info(
                f"Document ID: {document_id}, Components: {storage_result['component_count']}"
            )

            return result

        except Exception as e:
            self.logger.error(f"File processing failed: {e!s}")
            return {
                "success": False,
                "error": f"Processing failed: {e!s}",
                "details": {"exception_type": type(e).__name__},
            }

    async def process_file_from_url(
        self,
        file_url: str,
        user_id: str,
        knowledge_base_id: Optional[str] = None,
        mode: str = "simple",
        raw_file_url_to_return: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理来自URL的文件（重构版的mineru_process函数）

        Args:
            file_url: 文件URL
            user_id: 用户ID
            knowledge_base_id: 知识库ID，None时使用默认值
            mode: 处理模式 ("simple" 或 特定的OCR提供商名称)
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

            self.logger.info("=== Starting URL file processing ===")
            self.logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            self.logger.info(f"File URL: {file_url}")

            # 第一步：格式验证和PDF转换
            self.logger.info("=== Stage 1: Format validation and PDF conversion ===")

            validation_result = await self.format_pipeline.process_file_url_only(
                file_url
            )

            if not validation_result["success"]:
                self.logger.error(
                    f"Format validation failed: {validation_result['errors']}"
                )
                return None

            pdf_url = validation_result["pdf_url"]
            self.logger.info(f"PDF ready for processing: {pdf_url}")

            # 第二步：PDF处理和内容提取
            self.logger.info("=== Stage 2: PDF processing and content extraction ===")

            structured_content = (
                await self.pdf_pipeline.process_pdf_to_structured_content(
                    pdf_url=pdf_url,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    mode=mode,
                )
            )

            self.logger.info(
                f"Content extraction completed: {len(structured_content)} segments"
            )

            # 第三步：嵌入处理
            self.logger.info("=== Stage 3: Embedding processing ===")

            embedded_content = await self.embedding_service.embed_content_batch(
                structured_content
            )
            self.logger.info(
                f"Embedding processing completed for {len(embedded_content)} segments"
            )

            # 第四步：存储到向量数据库
            self.logger.info("=== Stage 4: Vector database storage ===")

            component_ids = (
                await self.storage_service.store_structured_content_to_vector_db(
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    document_name=filename,
                    structured_content=embedded_content,
                )
            )

            self.logger.info(
                f"Vector database storage completed: {len(component_ids)} components stored"
            )

            # 第五步：云端存储处理结果
            self.logger.info("=== Stage 5: Cloud storage ===")

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

            self.logger.info("=== URL file processing completed successfully ===")
            self.logger.info(
                f"Document ID: {document_id}, Components: {len(component_ids)}"
            )
            self.logger.info(f"Markdown URL: {file_urls['markdown_public_url']}")
            self.logger.info(f"PDF URL: {file_urls['pdf_file_public_url']}")

            return result

        except Exception as e:
            self.logger.error(f"URL file processing failed: {e!s}")
            return None

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": "DocumentProcessingService",
            "version": "1.0.0",
            "supported_modes": OCRProviderFactory.get_supported_providers(),
            "format_pipeline": self.format_pipeline.validator.SUPPORTED_FILE_TYPES,
            "pdf_pipeline": self.pdf_pipeline.get_pipeline_info(),
            "embedding_service": self.embedding_service.get_service_info(),
            "storage_service": self.storage_service.get_service_info(),
            "temp_directory": str(self.tmp_dir),
        }

    async def process_file_by_id(
        self,
        file_id: str,
        user_id: str,
        mode: str = "simple",
        parse_image_content: bool = False,
    ) -> Dict[str, Any]:
        """
        处理指定ID的文件内容

        Args:
            file_id: 文件ID
            user_id: 用户ID
            mode: 处理模式 ("simple" 或 特定的OCR提供商名称)
            parse_image_content: 是否解析图像内容到full_markdown

        Returns:
            处理结果字典
        """
        try:
            # 从数据库获取文件信息
            file_record = await unified_file_db_manager.get_file_record(file_id)
            if not file_record:
                raise ValueError(f"File not found: {file_id}")

            # 验证权限
            if file_record["user_id"] != user_id:
                raise PermissionError("Access denied: file belongs to another user")

            self.logger.info(f"Processing file by ID: {file_id}, Mode: {mode}")

            # 获取文件URL
            self.logger.info(f"File record: {file_record}")
            file_url = file_record.get("storage_path")
            derived_pdf_path = file_record.get("derived_pdf_path")
            self.logger.info(
                f"File URL obtained: {file_url}, Derived PDF path: {derived_pdf_path}"
            )
            if not file_url:
                raise ValueError(f"File URL not available for file: {file_id}")

            # 处理文件内容
            # 创建一个文档ID
            document_id = file_id

            # 使用配置中的MinIO地址和桶名构建文件URL
            minio_config = self.config.get("server_components", {}).get("minio", {})
            minio_address = minio_config.get("address", "localhost:9000")
            bucket_name = minio_config.get("bucket_name", "unifiles-bucket")
            # 优先使用转换后的PDF文件
            if derived_pdf_path:
                pdf_url = f"http://{minio_address}/{bucket_name}/" + derived_pdf_path
                self.logger.info(f"Using converted PDF file: {pdf_url}")
            else:
                file_url = f"http://{minio_address}/{bucket_name}/" + file_url
                pdf_url = file_url
                self.logger.info(f"Using original file: {pdf_url}")

            # 格式验证和PDF转换
            # /files上传文件端点现在已经实现了转PDF的功能
            # validation_result = await self.format_pipeline.process_file_url_only(
            #     file_url
            # )
            # if not validation_result["success"]:
            #     raise ValueError(
            #         f"Format validation failed: {validation_result['errors']}"
            #     )

            # pdf_url = validation_result["pdf_url"]
            self.logger.info(
                f"user_id {user_id}, document_id {document_id}, pdf_url {pdf_url}"
            )

            # PDF处理和内容提取
            structured_content = await self.pdf_pipeline.process_pdf_to_structured_content(
                pdf_url=pdf_url,
                user_id=user_id,
                knowledge_base_id=f"temp_{user_id}_{document_id}",  # 使用临时知识库ID
                document_id=document_id,
                mode=mode,
                parse_image_content=parse_image_content,
            )

            self.logger.info(f"Structured content: {structured_content}")

            # 使用未分块的完整Markdown，避免因分块（如重叠窗口）导致内容重复
            markdown_content = (
                self.pdf_pipeline.get_last_full_markdown()  # 由文本处理阶段缓存
                if hasattr(self.pdf_pipeline, "get_last_full_markdown")
                else None
            ) or "".join(item["content"] for item in structured_content)

            self.logger.info("=== Stage: Database Persistence ===")

            # === 数据库持久化逻辑 ===
            # 1. 解析图片资源
            image_assets = parse_image_assets_from_markdown(markdown_content)
            self.logger.info(f"Parsed {len(image_assets)} image assets from markdown")

            # 2. 创建或获取处理策略
            strategy_id = await extraction_db_manager.create_or_get_processing_strategy(
                strategy_name=f"OCR-{mode}",
                strategy_type="ocr",
                processing_config={
                    "method": mode,
                    "version": "1.0.0",
                    "engine": mode if mode != "simple" else "pdfplumber",
                },
            )
            self.logger.info(f"Using processing strategy: {strategy_id}")

            # 3. 创建提取文档记录
            extraction_id = await extraction_db_manager.create_extracted_document(
                file_id=file_id,
                user_id=user_id,
                extraction_strategy_id=strategy_id,
                full_markdown=markdown_content,
                total_chars=len(markdown_content),
                total_pages=0,  # 可以从structured_content中计算
                total_assets=len(image_assets),
                extraction_metadata={
                    "mode": mode,
                    "segments_count": len(structured_content),
                    "processed_at": datetime.now().isoformat(),
                },
                extraction_status="completed",
            )
            self.logger.info(f"Created extracted document: {extraction_id}")

            # 4. 创建提取资源记录（图片）
            asset_ids = []
            for img_asset in image_assets:
                try:
                    # 从文件名推断格式
                    filename = img_asset["filename"]
                    file_format = filename.split(".")[-1] if "." in filename else None

                    # 推断MIME类型
                    mime_type = None
                    if file_format:
                        mime_map = {
                            "png": "image/png",
                            "jpg": "image/jpeg",
                            "jpeg": "image/jpeg",
                            "gif": "image/gif",
                            "webp": "image/webp",
                        }
                        mime_type = mime_map.get(file_format.lower())

                    asset_id = await extraction_db_manager.create_extracted_asset(
                        extracted_document_id=extraction_id,
                        asset_type="image",
                        storage_path=img_asset["object_path"],
                        asset_name=filename,
                        original_filename=filename,
                        format=file_format,
                        mime_type=mime_type,
                        position_in_document=img_asset["index"],
                        alt_text=img_asset["alt_text"],
                    )
                    asset_ids.append(asset_id)
                    self.logger.debug(f"Created asset {asset_id} for image {filename}")
                except Exception as asset_error:
                    self.logger.warning(
                        f"Failed to create asset for {img_asset.get('filename')}: {asset_error}"
                    )

            self.logger.info(f"Created {len(asset_ids)} extracted assets")

            # 5. 记录处理日志
            await extraction_db_manager.create_process_log(
                entity_id=extraction_id,
                entity_type="document",
                process_type="extraction",
                action="extract_content",
                status="completed",
                log_type="log",
                log_level="info",
                process_stage="content_extraction",
                message=f"Successfully extracted {len(markdown_content)} characters from file {file_id} using {mode} mode",
                input_params={"file_id": file_id, "mode": mode},
                output_results={
                    "extraction_id": extraction_id,
                    "markdown_length": len(markdown_content),
                    "segments_count": len(structured_content),
                    "assets_count": len(asset_ids),
                },
                user_id=user_id,
            )

            self.logger.info(
                f"Extracted document persisted to database: {extraction_id} for file: {file_id}"
            )

            # 构建返回结果
            return {
                "extraction_id": extraction_id,  # 返回真实的数据库ID
                "content_type": "text/markdown",
                "extracted_text": "\n".join(
                    [item["content"] for item in structured_content]
                ),
                "markdown_content": markdown_content,
                "structured_data": {
                    "segments": len(structured_content),
                    "extracted_images_count": len(image_assets),
                    "extracted_assets": asset_ids,
                },
                "document_name": file_record.get("filename", "document"),
            }

        except Exception as e:
            self.logger.error(f"Error processing file by ID {file_id}: {e!s}")
            raise


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
