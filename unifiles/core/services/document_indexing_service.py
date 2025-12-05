"""
文档索引服务
负责将提取的文档内容分块、嵌入、索引到知识库
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from unifiles.core.logging import get_logger

logger = get_logger()

import re

import jieba

from ..config.env_config import read_config
from ..database import extraction_db_manager, unified_kb_db_manager
from ..database.models import (
    ChunkModel,
    ComponentModel,
    ComponentType,
    DocumentModel,
    PhotoModel,
)
from .chunking_service import get_chunking_service
from .embedding_service import get_embedding_service


class DocumentIndexingService:
    """文档索引服务主类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.chunking_service = get_chunking_service(config)
        self.embedding_service = get_embedding_service(config)
        self.kb_manager = unified_kb_db_manager
        self.extraction_manager = extraction_db_manager

        logger.info("DocumentIndexingService initialized")

    async def index_extracted_document_to_kb(
        self,
        extraction_id: str,
        kb_id: str,
        user_id: str,
        chunk_strategy: Optional[str] = None,
        document_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将提取的文档索引到知识库（支持重复索引）

        完整流程：
        1. 验证并获取提取文档和知识库信息
        2. 检查是否已存在（如存在则删除旧文档并重新索引）
        3. 获取分块配置
        4. 分块处理
        5. 创建文档记录
        6. 为每个块生成嵌入并存储
        7. 更新文档状态
        8. 更新统计信息
        9. 记录处理日志
        10. 返回结果

        重复索引行为：
        - 如果同一个extraction_id已经在该知识库中索引过
        - 系统会自动删除旧文档及其所有组件（CASCADE）
        - 然后使用新的分块策略重新索引
        - KB统计会先减少再增加，保持准确性

        Args:
            extraction_id: 提取文档ID
            kb_id: 知识库ID
            user_id: 用户ID
            chunk_strategy: 分块策略（可选，覆盖KB默认配置）
            document_title: 文档标题（可选）

        Returns:
            索引结果字典，包含document_id、chunk_count等信息

        Raises:
            ValueError: 如果提取文档或知识库不存在
            PermissionError: 如果用户无权限
        """
        try:
            logger.info(
                f"Starting document indexing: extraction_id={extraction_id}, "
                f"kb_id={kb_id}, user_id={user_id}"
            )

            # === Step 1: 验证并获取数据 ===
            extracted_doc = await self._get_and_validate_extraction(
                extraction_id, user_id
            )
            kb = await self._get_and_validate_kb(kb_id, user_id)

            # === Step 2: 检查是否已存在（处理重复索引）===
            existing_doc = await self.kb_manager.get_document_by_extraction(
                kb_id, extraction_id
            )

            is_reindexing = False
            old_document_id = None
            deletion_stats = None

            if existing_doc:
                logger.info(
                    f"Document already exists in KB (doc_id={existing_doc.id}), "
                    f"proceeding with re-indexing"
                )
                is_reindexing = True
                old_document_id = existing_doc.id

                # 删除旧文档及其组件（CASCADE自动删除）
                deletion_stats = await self.kb_manager.delete_document(existing_doc.id)
                logger.info(f"Deleted old document: {deletion_stats}")

                # 减少知识库统计（为重新索引做准备）
                await self.kb_manager.update_kb_statistics(
                    kb_id,
                    increment_documents=-deletion_stats["document_count"],
                    increment_components=-deletion_stats["component_count"],
                    increment_chunks=-deletion_stats["chunk_count"],
                    increment_photos=-deletion_stats["photo_count"],
                )
                logger.info("KB statistics decremented for re-indexing")

            # === Step 3: 获取分块配置 ===
            chunking_config = self._get_chunking_config(kb, chunk_strategy)
            logger.info(f"Using chunking config: {chunking_config}")

            # === Step 4: 分块处理 ===
            chunks = self.chunking_service.chunk_markdown(
                markdown=extracted_doc["full_markdown"],
                strategy=chunking_config["strategy_type"],
                max_chunk_size=chunking_config.get("max_chunk_size", 1000),
                min_chunk_size=chunking_config.get("min_chunk_size", 50),
                overlap_size=chunking_config.get("overlap_size", 100),
                split_on_headers=chunking_config.get("split_on_headers", True),
                preserve_structure=chunking_config.get("preserve_structure", True),
            )

            if not chunks:
                logger.warning(
                    f"No chunks generated for extraction {extraction_id}, aborting indexing"
                )
                raise ValueError("No content to index")

            logger.info(f"Generated {len(chunks)} chunks")

            # === Step 5: 创建文档记录 ===
            document_id = str(uuid.uuid4())
            doc_model = DocumentModel(
                id=document_id,
                knowledge_base_id=kb_id,
                extracted_document_id=extraction_id,
                title=document_title or extracted_doc.get("file_id", "Untitled"),
                processing_status="processing",
                indexing_status="indexing",
                chunking_strategy=chunking_config,
            )

            await self.kb_manager.create_document(doc_model)
            logger.info(f"Created document record: {document_id}")

            # === Step 6: 处理每个块（嵌入 + 存储）===
            text_chunk_count = 0
            photo_chunk_count = 0

            for chunk in chunks:
                try:
                    if chunk["type"] == "text":
                        await self._process_text_chunk(
                            chunk, document_id, extraction_id
                        )
                        text_chunk_count += 1
                    elif chunk["type"] == "image":
                        await self._process_image_chunk(
                            chunk, document_id, extraction_id
                        )
                        photo_chunk_count += 1
                except Exception as chunk_error:
                    logger.error(
                        f"Error processing chunk {chunk['index']}: {chunk_error}"
                    )
                    # 继续处理其他块，不中断整个流程

            total_chunk_count = text_chunk_count + photo_chunk_count
            logger.info(
                f"Processed {total_chunk_count} chunks: "
                f"{text_chunk_count} text, {photo_chunk_count} images"
            )

            # === Step 7: 更新文档状态 ===
            await self.kb_manager.update_document_status(
                document_id,
                processing_status="completed",
                indexing_status="completed",
                chunk_count=text_chunk_count,
                photo_count=photo_chunk_count,
                component_count=total_chunk_count,
            )

            # === Step 8: 更新知识库统计 ===
            await self.kb_manager.update_kb_statistics(
                kb_id,
                increment_documents=1,
                increment_components=total_chunk_count,
                increment_chunks=text_chunk_count,
                increment_photos=photo_chunk_count,
            )

            # === Step 9: 记录处理日志 ===
            log_action = (
                "re-index_to_knowledge_base"
                if is_reindexing
                else "index_to_knowledge_base"
            )
            log_message = (
                f"Successfully re-indexed document to KB {kb_id} (replaced {old_document_id})"
                if is_reindexing
                else f"Successfully indexed document to KB {kb_id}"
            )

            log_input_params = {
                "extraction_id": extraction_id,
                "kb_id": kb_id,
                "chunk_strategy": chunking_config["strategy_type"],
            }
            if is_reindexing:
                log_input_params["is_reindexing"] = True
                log_input_params["old_document_id"] = old_document_id
                log_input_params["deletion_stats"] = deletion_stats

            await self.extraction_manager.create_process_log(
                entity_id=document_id,
                entity_type="document",
                process_type="indexing",
                action=log_action,
                status="completed",
                log_type="log",
                log_level="info",
                process_stage="document_indexing",
                message=log_message,
                input_params=log_input_params,
                output_results={
                    "document_id": document_id,
                    "total_chunks": total_chunk_count,
                    "text_chunks": text_chunk_count,
                    "photo_chunks": photo_chunk_count,
                },
                user_id=user_id,
                start_time=datetime.now(),
                end_time=datetime.now(),
            )

            logger.info(f"Document indexing completed: {document_id}")

            # === Step 10: 返回结果 ===
            return {
                "document_id": document_id,
                "extraction_id": extraction_id,
                "knowledge_base_id": kb_id,
                "chunk_count": text_chunk_count,
                "photo_count": photo_chunk_count,
                "total_components": total_chunk_count,
                "indexing_status": "completed",
                "created_at": datetime.now().isoformat(),
                "chunking_strategy": chunking_config["strategy_type"],
            }

        except Exception as e:
            logger.exception(f"Document indexing failed: {e}")
            # 记录错误日志
            try:
                await self.extraction_manager.create_process_log(
                    entity_id=extraction_id,
                    entity_type="document",
                    process_type="indexing",
                    action="index_to_knowledge_base",
                    status="failed",
                    log_type="error",
                    log_level="error",
                    process_stage="document_indexing",
                    message=f"Document indexing failed: {e!s}",
                    error_details={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    input_params={
                        "extraction_id": extraction_id,
                        "kb_id": kb_id,
                    },
                    user_id=user_id,
                )
            except Exception as log_error:
                logger.error(f"Failed to create error log: {log_error}")

            raise

    async def _get_and_validate_extraction(
        self, extraction_id: str, user_id: str
    ) -> Dict[str, Any]:
        """获取并验证提取文档"""
        extracted_doc = await self.extraction_manager.get_extracted_document(
            extraction_id, user_id
        )

        if not extracted_doc:
            raise ValueError(f"Extraction not found: {extraction_id}")

        if extracted_doc["user_id"] != user_id:
            raise PermissionError(
                f"Access denied: extraction {extraction_id} belongs to another user"
            )

        if extracted_doc["extraction_status"] != "completed":
            raise ValueError(
                f"Extraction not completed: status={extracted_doc['extraction_status']}"
            )

        return extracted_doc

    async def _get_and_validate_kb(
        self, kb_id: str, user_id: str
    ) -> Any:  # Returns KnowledgeBaseModel
        """获取并验证知识库"""
        kb = await self.kb_manager.get_knowledge_base(kb_id)

        if not kb:
            raise ValueError(f"Knowledge base not found: {kb_id}")

        if kb.user_id != user_id:
            raise PermissionError(
                f"Access denied: knowledge base {kb_id} belongs to another user"
            )

        return kb

    def _get_chunking_config(
        self, kb: Any, chunk_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取分块配置

        优先级：请求参数 > KB默认配置 > 系统默认配置
        """
        # 系统默认配置
        default_config = {
            "strategy_type": "markdown_hierarchical",
            "max_chunk_size": 1000,
            "overlap_size": 100,
            "min_chunk_size": 50,
            "preserve_structure": True,
            "split_on_headers": True,
        }

        # KB默认配置
        kb_config = kb.default_chunking_strategy or {}

        # 合并配置
        config = {**default_config, **kb_config}

        # 请求覆盖
        if chunk_strategy:
            config["strategy_type"] = chunk_strategy

        return config

    async def _process_text_chunk(
        self, chunk: Dict[str, Any], document_id: str, extraction_id: str
    ) -> None:
        """
        处理文本块：生成嵌入 + 存储到数据库

        Args:
            chunk: 文本块数据
            document_id: 文档ID
            extraction_id: 提取文档ID
        """
        component_id = str(uuid.uuid4())
        chunk_id = str(uuid.uuid4())

        try:
            # 生成嵌入向量
            logger.debug(f"Generating embedding for text chunk {chunk['index']}")
            embedding = await self.embedding_service.embed_single_text(chunk["content"])

            # 创建组件记录
            component = ComponentModel(
                id=component_id,
                document_id=document_id,
                component_type=ComponentType.CHUNK,
                component_index=chunk["index"],
                content=chunk["content"],
                embedding=embedding,
                search_keywords=self._generate_keywords(chunk["content"]),
            )
            await self.kb_manager.create_component(component)

            # 创建文本块子类记录
            chunk_model = ChunkModel(
                id=chunk_id,
                component_id=component_id,
                text_content=chunk["content"],
                char_count=chunk["metadata"].get("char_count", len(chunk["content"])),
            )
            await self.kb_manager.create_chunk(chunk_model)

            logger.debug(
                f"Text chunk {chunk['index']} processed: "
                f"component_id={component_id}, chunk_id={chunk_id}"
            )

        except Exception as e:
            logger.error(
                f"Error processing text chunk {chunk['index']} "
                f"(component_id={component_id}): {e}"
            )
            raise

    async def _process_image_chunk(
        self, chunk: Dict[str, Any], document_id: str, extraction_id: str
    ) -> None:
        """
        处理图片块：查找资源 + 生成嵌入 + 存储到数据库

        Args:
            chunk: 图片块数据
            document_id: 文档ID
            extraction_id: 提取文档ID
        """
        component_id = str(uuid.uuid4())
        photo_id = str(uuid.uuid4())

        try:
            # 图片描述作为内容
            image_description = chunk["metadata"].get("alt_text", "")
            image_path = chunk["metadata"].get("image_path", "")

            # 生成嵌入（基于描述文本）
            logger.debug(f"Generating embedding for image chunk {chunk['index']}")
            if image_description:
                embedding = await self.embedding_service.embed_single_text(
                    image_description
                )
            else:
                # 如果没有描述，使用图片路径作为描述
                embedding = await self.embedding_service.embed_single_text(
                    f"Image: {image_path}"
                )

            # 创建组件记录
            component = ComponentModel(
                id=component_id,
                document_id=document_id,
                component_type=ComponentType.PHOTO,
                component_index=chunk["index"],
                content=image_description or image_path,
                embedding=embedding,
                search_keywords=self._generate_keywords(
                    image_description or image_path
                ),
            )
            await self.kb_manager.create_component(component)

            # 创建图片块子类记录
            photo_model = PhotoModel(
                id=photo_id,
                component_id=component_id,
                extracted_asset_id=None,  # TODO: 关联到 extracted_assets 表
                photo_description=image_description,
                alt_text=chunk["metadata"].get("alt_text"),
                photo_subtype="image",
            )
            await self.kb_manager.create_photo(photo_model)

            logger.debug(
                f"Image chunk {chunk['index']} processed: "
                f"component_id={component_id}, photo_id={photo_id}"
            )

        except Exception as e:
            logger.error(
                f"Error processing image chunk {chunk['index']} "
                f"(component_id={component_id}): {e}"
            )
            raise

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": "DocumentIndexingService",
            "version": "1.0.0",
            "chunking_service": self.chunking_service.get_service_info(),
            "embedding_service": self.embedding_service.get_service_info(),
        }

    def _generate_keywords(self, text: str) -> List[str]:
        """
        Generate search keywords from text using jieba.
        """
        if not text:
            return []

        # Use jieba for word segmentation
        words = jieba.lcut(text.lower())

        # Filter out short words (length < 2) and non-word characters
        # We keep words that have at least 2 characters and contain at least one alphanumeric/Chinese char
        keywords = [
            w for w in words if len(w) >= 2 and re.search(r"[\w\u4e00-\u9fff]", w)
        ]

        # Remove duplicates while preserving order
        return list(dict.fromkeys(keywords))


# 默认文档索引服务实例
_default_document_indexing_service: Optional[DocumentIndexingService] = None


def get_document_indexing_service(
    config: Optional[Dict[str, Any]] = None,
) -> DocumentIndexingService:
    """获取默认文档索引服务实例（单例模式）"""
    global _default_document_indexing_service
    if _default_document_indexing_service is None:
        _default_document_indexing_service = DocumentIndexingService(config=config)
    return _default_document_indexing_service
