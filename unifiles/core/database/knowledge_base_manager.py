"""
知识库数据库管理器
负责知识库、文档、组件（components/chunks/photos）的数据库操作

对齐数据库表结构（见 scripts/sql/*）：
- 文档使用表 unifiles.documents（必须包含 extracted_document_id 外键）
- 组件抽象层使用表 unifiles.components，子类表 unifiles.chunks / unifiles.photos
"""

import json
from datetime import datetime
from typing import Optional

from loguru import logger

from .base_manager import BaseDBManager
from .models import (
    ChunkModel,
    ComponentModel,
    ComponentType,
    DocumentModel,
    FileModel,
    FileProcessingLogModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingStage,
    ProcessingStatus,
)


class KnowledgeBaseDBManager(BaseDBManager):
    """知识库数据库管理器 - 提供知识库、文档、组件的完整操作"""

    # ==================== 知识库操作 ====================

    async def create_knowledge_base(
        self, kb_model: KnowledgeBaseModel
    ) -> KnowledgeBaseModel:
        """创建知识库"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.knowledge_bases (id, user_id, name, description, document_ids)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        kb_model.id,
                        kb_model.user_id,
                        kb_model.name,
                        kb_model.description,
                        kb_model.document_ids,
                    )

                    # 获取创建的知识库信息
                    result = await conn.fetchrow(
                        "SELECT * FROM unifiles.knowledge_bases WHERE id = $1",
                        kb_model.id,
                    )

                    if result:
                        kb_model.created_at = result["created_at"]
                        kb_model.updated_at = result["updated_at"]

                    logger.info(f"Knowledge base created: {kb_model.id}")
                    return kb_model

            except Exception as e:
                logger.error(f"Error creating knowledge base {kb_model.id}: {e}")
                raise

    async def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBaseModel]:
        """获取知识库信息"""
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.knowledge_bases WHERE id = $1", kb_id
                )

                if result:
                    return KnowledgeBaseModel(
                        id=result["id"],
                        user_id=result["user_id"],
                        name=result["name"],
                        description=result["description"] or "",
                        document_ids=json.loads(result["document_ids"] or "[]"),
                        created_at=result["created_at"],
                        updated_at=result["updated_at"],
                    )
                return None

            except Exception as e:
                logger.error(f"Error getting knowledge base {kb_id}: {e}")
                raise

    async def list_knowledge_bases(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[KnowledgeBaseModel], int]:
        """列出用户的知识库（分页）并返回总数。

        与 scripts/sql/051-create-knowledge-base.sql 对齐：依据 user_id 过滤，按创建时间倒序。
        """
        # 参数校验与清理
        user_id = self.sanitize_input(user_id)
        self.validate_pagination(limit, offset)

        # 查询列表
        rows = await self.fetch_many(
            """
            SELECT *
            FROM unifiles.knowledge_bases
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

        # 查询总数
        total_count = await self.fetch_value(
            "SELECT COUNT(*) FROM unifiles.knowledge_bases WHERE user_id = $1",
            user_id,
        )

        # 映射为模型（仅填充当前API所需字段，其他留默认）
        items: list[KnowledgeBaseModel] = []
        for r in rows:
            items.append(
                KnowledgeBaseModel(
                    id=r["id"],
                    user_id=r["user_id"],
                    name=r["name"],
                    description=r.get("description") or "",
                    document_count=r.get("document_count", 0),
                    document_ids=json.loads(r.get("document_ids") or "[]"),
                    created_at=r.get("created_at"),
                    updated_at=r.get("updated_at"),
                )
            )

        # fetch_value 可能返回 Decimal/Int，统一为 int
        try:
            total_count = int(total_count or 0)
        except Exception:
            total_count = 0

        return items, total_count

    async def ensure_knowledge_base_exists(
        self, kb_id: str, user_id: str, name: Optional[str] = None
    ) -> KnowledgeBaseModel:
        """确保知识库存在，不存在则创建"""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            kb = KnowledgeBaseModel(
                id=kb_id,
                user_id=user_id,
                name=name or f"Knowledge Base {kb_id}",
                description=f"Auto-created knowledge base for user {user_id}",
            )
            kb = await self.create_knowledge_base(kb)
        return kb

    # ==================== 文档操作 ====================

    async def create_document(self, doc_model: DocumentModel) -> DocumentModel:
        """创建文档（对齐 scripts/sql/051-create-knowledge-base.sql）

        注意：documents 表要求 extracted_document_id 非空，且为外键。
        """
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.documents (
                            id, knowledge_base_id, extracted_document_id,
                            title, display_name, description,
                            chunking_strategy, custom_config, access_level,
                            hierarchy_path
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::ltree)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        doc_model.id,
                        doc_model.knowledge_base_id,
                        doc_model.extracted_document_id,
                        getattr(doc_model, "title", None),
                        getattr(doc_model, "display_name", None),
                        getattr(doc_model, "description", None),
                        getattr(doc_model, "chunking_strategy", None),
                        getattr(doc_model, "custom_config", {}),
                        getattr(doc_model, "access_level", "inherited"),
                        getattr(doc_model, "hierarchy_path", "root"),
                    )

                    # 获取创建的文档信息
                    result = await conn.fetchrow(
                        "SELECT * FROM unifiles.documents WHERE id = $1",
                        doc_model.id,
                    )

                    if result:
                        doc_model.created_at = result["created_at"]
                        doc_model.updated_at = result["updated_at"]

                    logger.info(f"Document created: {doc_model.id}")
                    return doc_model

            except Exception as e:
                logger.error(f"Error creating document {doc_model.id}: {e}")
                raise

    async def get_document(self, doc_id: str) -> Optional[DocumentModel]:
        """获取文档信息（对齐新表结构）"""
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.documents WHERE id = $1", doc_id
                )

                if result:
                    return DocumentModel(
                        id=result["id"],
                        knowledge_base_id=result["knowledge_base_id"],
                        extracted_document_id=result["extracted_document_id"],
                        title=result.get("title"),
                        display_name=result.get("display_name"),
                        description=result.get("description") or "",
                        chunking_strategy=result.get("chunking_strategy"),
                        custom_config=result.get("custom_config") or {},
                        access_level=result.get("access_level", "inherited"),
                        hierarchy_path=str(result.get("hierarchy_path", "root")),
                        created_at=result.get("created_at"),
                        processed_at=result.get("processed_at"),
                        indexed_at=result.get("indexed_at"),
                        updated_at=result.get("updated_at"),
                        last_accessed_at=result.get("last_accessed_at"),
                    )
                return None

            except Exception as e:
                logger.error(f"Error getting document {doc_id}: {e}")
                raise

    async def ensure_document_exists(
        self,
        doc_id: str,
        kb_id: str,
        extracted_document_id: Optional[str] = None,
        *,
        title: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> DocumentModel:
        """确保文档存在；若不存在且提供了 extracted_document_id 则创建。

        按新表结构，documents 需要 extracted_document_id 外键；若未提供则抛出错误。
        """
        existing = await self.get_document(doc_id)
        if existing:
            return existing

        if not extracted_document_id:
            raise ValueError(
                "Document does not exist and cannot be auto-created without extracted_document_id"
            )

        doc_model = DocumentModel(
            id=doc_id,
            knowledge_base_id=kb_id,
            extracted_document_id=extracted_document_id,
            title=title,
            display_name=display_name,
        )
        return await self.create_document(doc_model)

    async def update_document_urls(
        self, doc_id: str, markdown_url: str, raw_file_url: str
    ) -> bool:
        """更新文档URL信息（写入 documents.document_metadata.public_urls）"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    result = await conn.execute(
                        """
                        UPDATE unifiles.documents
                        SET document_metadata = COALESCE(document_metadata, '{}'::jsonb)
                            || jsonb_build_object(
                                'public_urls', jsonb_build_object(
                                    'markdown_public_url', $2,
                                    'raw_file_public_url', $3
                                )
                            )
                        WHERE id = $1
                        """,
                        doc_id,
                        markdown_url,
                        raw_file_url,
                    )

                    rows = int(result.split()[-1]) if result else 0
                    if rows == 0:
                        logger.warning(
                            f"No document updated for URLs; document may not exist: {doc_id}"
                        )
                    else:
                        logger.info(f"Document URLs updated: {doc_id}")
                    return rows > 0

            except Exception as e:
                logger.error(f"Error updating document URLs {doc_id}: {e}")
                raise

    # ==================== 文件操作 ====================

    async def create_file_record(self, file_model: FileModel) -> FileModel:
        """创建文件记录"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.files (
                            id, user_id, bytes, filename, mime_type,
                            storage_path, storage_config_id, status, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        file_model.id,
                        file_model.user_id,
                        file_model.bytes,
                        file_model.filename,
                        file_model.mime_type,
                        getattr(file_model, "storage_path", ""),
                        getattr(file_model, "storage_config_id", None),
                        file_model.status.value,
                        json.dumps(file_model.metadata or {}),
                    )

                    # 获取创建的文件信息
                    result = await conn.fetchrow(
                        "SELECT * FROM unifiles.files WHERE id = $1", file_model.id
                    )

                    if result:
                        file_model.created_at = result["created_at"]

                    logger.info(f"File record created: {file_model.id}")
                    return file_model

            except Exception as e:
                logger.error(f"Error creating file record {file_model.id}: {e}")
                raise

    async def get_file_record(self, file_id: str) -> Optional[FileModel]:
        """获取文件记录（与文件表结构对齐）"""
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    """
                    SELECT id, user_id, filename, bytes, mime_type, storage_path,
                           status, metadata, created_at
                    FROM unifiles.files WHERE id = $1
                    """,
                    file_id,
                )

                if result:
                    return FileModel(
                        id=result["id"],
                        user_id=result["user_id"],
                        filename=result["filename"],
                        bytes=result["bytes"],
                        mime_type=result.get("mime_type"),
                        storage_path=result.get("storage_path", ""),
                        status=FileStatus(result.get("status", "active")),
                        metadata=json.loads(result.get("metadata") or "{}"),
                        created_at=result["created_at"],
                    )
                return None

            except Exception as e:
                logger.error(f"Error getting file record {file_id}: {e}")
                raise

    # ==================== 文本块操作 ====================

    async def create_component(self, component: ComponentModel) -> ComponentModel:
        """创建组件（components 表）"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    embedding_vector = None
                    if component.embedding is not None:
                        embedding_vector = (
                            f"[{','.join(map(str, component.embedding))}]"
                        )
                    await conn.execute(
                        """
                        INSERT INTO unifiles.components (
                            id, document_id, component_type, component_index,
                            content, embedding, embedding_dimensions
                        ) VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
                        """,
                        component.id,
                        component.document_id,
                        component.component_type.value
                        if hasattr(component.component_type, "value")
                        else str(component.component_type),
                        component.component_index,
                        component.content,
                        embedding_vector,
                        (len(component.embedding) if component.embedding else None),
                    )
                    logger.info(
                        f"Component created: {component.id} ({component.component_type})"
                    )
                    return component
            except Exception as e:
                logger.error(f"Error creating component {component.id}: {e}")
                raise

    async def create_chunk(self, chunk_model: ChunkModel) -> ChunkModel:
        """创建文本块（chunks 子表）"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.chunks (
                            id, component_id, text_content
                        ) VALUES ($1, $2, $3)
                        """,
                        chunk_model.id,
                        chunk_model.component_id,
                        chunk_model.text_content,
                    )
                    logger.info(f"Chunk created: {chunk_model.id}")
                    return chunk_model
            except Exception as e:
                logger.error(f"Error creating chunk {chunk_model.id}: {e}")
                raise

    # ==================== 图片操作 ====================

    async def create_photo(self, photo_model: PhotoModel) -> PhotoModel:
        """创建图片记录（photos 子表）"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.photos (
                            id, component_id, extracted_asset_id,
                            photo_description, alt_text, photo_subtype,
                            width, height, file_size, format
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        photo_model.id,
                        photo_model.component_id,
                        getattr(photo_model, "extracted_asset_id", None),
                        getattr(photo_model, "photo_description", None),
                        getattr(photo_model, "alt_text", None),
                        getattr(photo_model, "photo_subtype", "image"),
                        getattr(photo_model, "width", None),
                        getattr(photo_model, "height", None),
                        getattr(photo_model, "file_size", None),
                        getattr(photo_model, "format", None),
                    )
                    logger.info(f"Photo created: {photo_model.id}")
                    return photo_model
            except Exception as e:
                logger.error(f"Error creating photo {photo_model.id}: {e}")
                raise

    # ==================== 处理日志操作 ====================

    async def create_processing_log(
        self, log_model: FileProcessingLogModel
    ) -> FileProcessingLogModel:
        """创建处理日志"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.file_processing_logs
                        (id, file_id, stage, status, message, error_details)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        log_model.id,
                        log_model.file_id,
                        log_model.stage.value,
                        log_model.status.value,
                        log_model.message,
                        json.dumps(log_model.error_details or {}),
                    )

                    # 获取创建的日志信息
                    result = await conn.fetchrow(
                        "SELECT * FROM unifiles.file_processing_logs WHERE id = $1",
                        log_model.id,
                    )

                    if result:
                        log_model.created_at = result["created_at"]

                    logger.info(f"Processing log created: {log_model.id}")
                    return log_model

            except Exception as e:
                logger.error(f"Error creating processing log {log_model.id}: {e}")
                raise

    async def update_processing_log(
        self,
        log_id: str,
        status: ProcessingStatus,
        message: Optional[str] = None,
        error_info: Optional[dict] = None,
    ) -> bool:
        """更新处理日志状态"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE unifiles.file_processing_logs
                        SET status = $2, message = $3, error_details = $4
                        WHERE id = $1
                        """,
                        log_id,
                        status.value,
                        message,
                        json.dumps(error_info or {}),
                    )

                    logger.info(f"Processing log updated: {log_id} -> {status.value}")
                    return True

            except Exception as e:
                logger.error(f"Error updating processing log {log_id}: {e}")
                raise


# 全局实例
unified_kb_db_manager = KnowledgeBaseDBManager()
