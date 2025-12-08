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

from unifiles.core.logging import get_logger

logger = get_logger()

from .base_manager import BaseDBManager
from .helpers import (
    parse_db_result_count,
    parse_json_field,
    parse_string_list,
    safe_int,
    to_json_string,
)
from .models import (
    ChunkModel,
    ComponentModel,
    DocumentModel,
    FileProcessingLogModel,
    KnowledgeBaseModel,
    PhotoModel,
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
                        document_ids=parse_string_list(result.get("document_ids")),
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

        # 映射为模型
        items: list[KnowledgeBaseModel] = [
            KnowledgeBaseModel(
                id=r["id"],
                user_id=r["user_id"],
                name=r["name"],
                description=r.get("description") or "",
                document_count=r.get("document_count", 0),
                document_ids=parse_string_list(r.get("document_ids")),
                created_at=r.get("created_at"),
                updated_at=r.get("updated_at"),
            )
            for r in rows
        ]

        return items, safe_int(total_count)

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
                    # Normalize JSON fields to strings for safe binding
                    _chunking = to_json_string(
                        getattr(doc_model, "chunking_strategy", None)
                    )
                    _custom_cfg = to_json_string(
                        getattr(doc_model, "custom_config", {})
                    )

                    await conn.execute(
                        """
                        INSERT INTO unifiles.documents (
                            id, knowledge_base_id, extracted_document_id,
                            title, display_name, description,
                            chunking_strategy, custom_config, access_level,
                            hierarchy_path
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6,
                            $7::jsonb, $8::jsonb, $9, $10::ltree
                        )
                        ON CONFLICT (id) DO NOTHING
                        """,
                        doc_model.id,
                        doc_model.knowledge_base_id,
                        doc_model.extracted_document_id,
                        getattr(doc_model, "title", None),
                        getattr(doc_model, "display_name", None),
                        getattr(doc_model, "description", None),
                        _chunking,
                        _custom_cfg,
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
                        chunking_strategy=parse_json_field(
                            result.get("chunking_strategy")
                        ),
                        custom_config=parse_json_field(result.get("custom_config")),
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

    async def get_document_by_extraction(
        self, kb_id: str, extraction_id: str
    ) -> Optional[DocumentModel]:
        """
        根据知识库ID和提取文档ID查询文档

        用于检测重复索引场景

        Args:
            kb_id: 知识库ID
            extraction_id: 提取文档ID

        Returns:
            DocumentModel if found, None otherwise
        """
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    """
                    SELECT * FROM unifiles.documents
                    WHERE knowledge_base_id = $1 AND extracted_document_id = $2
                    """,
                    kb_id,
                    extraction_id,
                )

                if result:
                    return DocumentModel(
                        id=result["id"],
                        knowledge_base_id=result["knowledge_base_id"],
                        extracted_document_id=result["extracted_document_id"],
                        title=result.get("title"),
                        display_name=result.get("display_name"),
                        description=result.get("description") or "",
                        chunking_strategy=parse_json_field(
                            result.get("chunking_strategy")
                        ),
                        custom_config=parse_json_field(result.get("custom_config")),
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
                logger.error(
                    f"Error getting document by extraction (kb={kb_id}, extraction={extraction_id}): {e}"
                )
                raise

    async def list_documents(
        self, kb_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[DocumentModel], int]:
        """列出指定知识库下的文档（分页）并返回总数。"""
        # 参数校验与清理
        kb_id = self.sanitize_input(kb_id)
        self.validate_pagination(limit, offset)

        # 查询文档列表
        rows = await self.fetch_many(
            """
            SELECT *
            FROM unifiles.documents
            WHERE knowledge_base_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            kb_id,
            limit,
            offset,
        )

        # 查询总数
        total_count = await self.fetch_value(
            "SELECT COUNT(*) FROM unifiles.documents WHERE knowledge_base_id = $1",
            kb_id,
        )

        items: list[DocumentModel] = [
            DocumentModel(
                id=r["id"],
                knowledge_base_id=r["knowledge_base_id"],
                extracted_document_id=r["extracted_document_id"],
                title=r.get("title"),
                display_name=r.get("display_name"),
                description=r.get("description") or "",
                chunking_strategy=parse_json_field(r.get("chunking_strategy")),
                custom_config=parse_json_field(r.get("custom_config")),
                access_level=r.get("access_level", "inherited"),
                hierarchy_path=str(r.get("hierarchy_path", "root")),
                processing_status=r.get("processing_status", "pending"),
                indexing_status=r.get("indexing_status", "pending"),
                component_count=r.get("component_count", 0),
                chunk_count=r.get("chunk_count", 0),
                photo_count=r.get("photo_count", 0),
                total_chars=r.get("total_chars", 0),
                total_tokens=r.get("total_tokens", 0),
                created_at=r.get("created_at"),
                processed_at=r.get("processed_at"),
                indexed_at=r.get("indexed_at"),
                updated_at=r.get("updated_at"),
                last_accessed_at=r.get("last_accessed_at"),
            )
            for r in rows
        ]

        return items, safe_int(total_count)

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

    async def delete_document(self, doc_id: str) -> dict[str, int]:
        """
        删除文档及其所有关联组件（级联删除）

        Args:
            doc_id: 文档ID

        Returns:
            删除的统计信息字典：
            {
                "document_count": 1,
                "component_count": N,
                "chunk_count": X,
                "photo_count": Y
            }

        Raises:
            ValueError: 如果文档不存在
        """
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    # 1. 先统计要删除的组件数量（用于更新KB统计）
                    component_stats = await conn.fetchrow(
                        """
                        SELECT
                            COUNT(*) as total_components,
                            COUNT(*) FILTER (WHERE component_type = 'chunk') as chunk_count,
                            COUNT(*) FILTER (WHERE component_type = 'photo') as photo_count
                        FROM unifiles.components
                        WHERE document_id = $1
                        """,
                        doc_id,
                    )

                    total_components = component_stats["total_components"] or 0
                    chunk_count = component_stats["chunk_count"] or 0
                    photo_count = component_stats["photo_count"] or 0

                    # 2. 删除文档（CASCADE会自动删除components、chunks、photos）
                    result = await conn.execute(
                        """
                        DELETE FROM unifiles.documents
                        WHERE id = $1
                        """,
                        doc_id,
                    )

                    rows_deleted = parse_db_result_count(result)

                    if rows_deleted == 0:
                        logger.warning(f"No document found to delete: {doc_id}")
                        raise ValueError(f"Document not found: {doc_id}")

                    logger.info(
                        f"Deleted document {doc_id}: "
                        f"{total_components} components "
                        f"({chunk_count} chunks, {photo_count} photos)"
                    )

                    return {
                        "document_count": 1,
                        "component_count": total_components,
                        "chunk_count": chunk_count,
                        "photo_count": photo_count,
                    }

            except Exception as e:
                logger.error(f"Error deleting document {doc_id}: {e}")
                raise

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

                    rows = parse_db_result_count(result)
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

    async def update_document_status(
        self,
        doc_id: str,
        processing_status: Optional[str] = None,
        indexing_status: Optional[str] = None,
        chunk_count: Optional[int] = None,
        photo_count: Optional[int] = None,
        component_count: Optional[int] = None,
    ) -> bool:
        """更新文档处理状态和统计信息

        Args:
            doc_id: 文档ID
            processing_status: 处理状态 (pending, processing, completed, failed, cancelled)
            indexing_status: 索引状态 (pending, indexing, completed, failed)
            chunk_count: 文本块数量
            photo_count: 图片数量
            component_count: 组件总数

        Returns:
            是否成功更新
        """
        async with await self.get_connection() as conn:
            try:
                # 构建动态更新语句
                update_fields = []
                values = [doc_id]
                param_count = 1

                if processing_status is not None:
                    param_count += 1
                    update_fields.append(f"processing_status = ${param_count}")
                    values.append(processing_status)

                if indexing_status is not None:
                    param_count += 1
                    update_fields.append(f"indexing_status = ${param_count}")
                    values.append(indexing_status)

                    # 如果索引完成，设置 indexed_at 时间戳
                    if indexing_status == "completed":
                        param_count += 1
                        update_fields.append(f"indexed_at = ${param_count}")
                        values.append(datetime.now())

                if chunk_count is not None:
                    param_count += 1
                    update_fields.append(f"chunk_count = ${param_count}")
                    values.append(chunk_count)

                if photo_count is not None:
                    param_count += 1
                    update_fields.append(f"photo_count = ${param_count}")
                    values.append(photo_count)

                if component_count is not None:
                    param_count += 1
                    update_fields.append(f"component_count = ${param_count}")
                    values.append(component_count)

                if not update_fields:
                    logger.warning(f"No fields to update for document {doc_id}")
                    return False

                # 添加 updated_at 时间戳
                param_count += 1
                update_fields.append(f"updated_at = ${param_count}")
                values.append(datetime.now())

                query = f"""
                    UPDATE unifiles.documents
                    SET {", ".join(update_fields)}
                    WHERE id = $1
                """

                async with conn.transaction():
                    result = await conn.execute(query, *values)
                    rows = parse_db_result_count(result)

                    if rows == 0:
                        logger.warning(
                            f"No document updated; document may not exist: {doc_id}"
                        )
                    else:
                        logger.info(f"Document status updated: {doc_id}")

                    return rows > 0

            except Exception as e:
                logger.error(f"Error updating document status {doc_id}: {e}")
                raise

    async def update_kb_statistics(
        self,
        kb_id: str,
        increment_documents: int = 0,
        increment_components: int = 0,
        increment_chunks: int = 0,
        increment_photos: int = 0,
    ) -> bool:
        """更新知识库统计信息（增量更新）

        Args:
            kb_id: 知识库ID
            increment_documents: 文档数增量
            increment_components: 组件数增量
            increment_chunks: 文本块数增量
            increment_photos: 图片数增量

        Returns:
            是否成功更新
        """
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    result = await conn.execute(
                        """
                        UPDATE unifiles.knowledge_bases
                        SET
                            document_count = document_count + $2,
                            component_count = component_count + $3,
                            chunk_count = chunk_count + $4,
                            photo_count = photo_count + $5,
                            updated_at = $6
                        WHERE id = $1
                        """,
                        kb_id,
                        increment_documents,
                        increment_components,
                        increment_chunks,
                        increment_photos,
                        datetime.now(),
                    )

                    rows = parse_db_result_count(result)
                    if rows == 0:
                        logger.warning(
                            f"No knowledge base updated; KB may not exist: {kb_id}"
                        )
                    else:
                        logger.info(
                            f"KB statistics updated: {kb_id} "
                            f"(+{increment_documents} docs, +{increment_components} components)"
                        )

                    return rows > 0

            except Exception as e:
                logger.error(f"Error updating KB statistics {kb_id}: {e}")
                raise

    async def delete_knowledge_base(self, kb_id: str) -> dict[str, bool]:
        """
        删除知识库及其所有关联数据。

        依赖数据库外键的 ON DELETE CASCADE 约束，自动清理：
        - documents（及其下游 components/chunks/photos）
        - kb_statistics 等引用 knowledge_bases 的表

        Args:
            kb_id: 知识库ID

        Returns:
            包含删除结果的字典，例如 {"deleted": True}

        Raises:
            ValueError: 当指定的知识库不存在时
        """
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    result = await conn.execute(
                        """
                        DELETE FROM unifiles.knowledge_bases
                        WHERE id = $1
                        """,
                        kb_id,
                    )

                    rows_deleted = parse_db_result_count(result)

                    if rows_deleted == 0:
                        logger.warning(f"No knowledge base found to delete: {kb_id}")
                        raise ValueError(f"Knowledge base not found: {kb_id}")

                    logger.info(f"Knowledge base deleted: {kb_id}")
                    return {"deleted": True}

            except Exception as e:
                logger.error(f"Error deleting knowledge base {kb_id}: {e}")
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
                            content, embedding, embedding_dimensions, search_keywords
                        ) VALUES ($1, $2, $3, $4, $5, $6::vector, $7, $8)
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
                        component.search_keywords,
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

    # ==================== 向量检索操作 ====================

    async def search_knowledge_base_vector(
        self,
        kb_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        include_photos: bool = False,
    ) -> list[dict]:
        """在知识库中进行向量检索

        Args:
            kb_id: 知识库ID
            query_embedding: 查询向量（与存储的embedding维度一致）
            top_k: 返回结果数量，默认10
            include_photos: 是否包含图片块在检索结果中，默认False

        Returns:
            检索结果列表，每项包含：
            - component_id: 组件ID（统一主键）
            - document_id: 文档ID
            - text_content: 文本内容或图片描述
            - similarity_score: 相似度分数（0-1，越大越相似）
            - component_type: 组件类型（chunk或photo）

        Raises:
            ValueError: 如果查询向量为空或知识库不存在
            Exception: 数据库查询失败
        """
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty")

        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        # 将Python列表转换为PostgreSQL向量字符串格式
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        async with await self.get_connection() as conn:
            try:
                if include_photos:
                    # 执行向量相似度检索，包含图片块
                    # 使用 <=> 操作符计算余弦距离（值越小越相似）
                    # 1 - distance 转换为相似度分数（0-1，越大越相似）
                    results = await conn.fetch(
                        """
                        SELECT
                            comp.id as component_id,
                            d.id as document_id,
                            CASE
                                WHEN comp.component_type = 'chunk' THEN c.text_content
                                WHEN comp.component_type = 'photo' THEN COALESCE(p.photo_description, p.alt_text, '')
                            END as text_content,
                            1 - (comp.embedding <=> $1::vector) as similarity_score,
                            comp.component_type
                        FROM unifiles.components comp
                        JOIN unifiles.documents d ON comp.document_id = d.id
                        LEFT JOIN unifiles.chunks c ON comp.id = c.component_id AND comp.component_type = 'chunk'
                        LEFT JOIN unifiles.photos p ON comp.id = p.component_id AND comp.component_type = 'photo'
                        WHERE d.knowledge_base_id = $2
                          AND comp.embedding IS NOT NULL
                          AND (comp.component_type = 'chunk' OR comp.component_type = 'photo')
                        ORDER BY comp.embedding <=> $1::vector ASC
                        LIMIT $3
                        """,
                        embedding_str,
                        kb_id,
                        top_k,
                    )
                else:
                    # 只检索文本块（保持原有逻辑）
                    results = await conn.fetch(
                        """
                        SELECT
                            comp.id as component_id,
                            d.id as document_id,
                            c.text_content,
                            1 - (comp.embedding <=> $1::vector) as similarity_score,
                            comp.component_type
                        FROM unifiles.components comp
                        JOIN unifiles.documents d ON comp.document_id = d.id
                        JOIN unifiles.chunks c ON comp.id = c.component_id
                        WHERE d.knowledge_base_id = $2
                          AND comp.component_type = 'chunk'
                          AND comp.embedding IS NOT NULL
                        ORDER BY comp.embedding <=> $1::vector ASC
                        LIMIT $3
                        """,
                        embedding_str,
                        kb_id,
                        top_k,
                    )

                # 转换结果为字典列表（仅对外暴露 component_id）
                search_results = [
                    {
                        "component_id": row["component_id"],
                        "document_id": row["document_id"],
                        "text_content": row["text_content"],
                        "similarity_score": float(row["similarity_score"]),
                        "component_type": row["component_type"],
                    }
                    for row in results
                ]

                logger.info(
                    f"Vector search completed for KB {kb_id}: "
                    f"found {len(search_results)} results (top_k={top_k}, include_photos={include_photos})"
                )

                return search_results

            except Exception as e:
                logger.error(f"Error performing vector search on KB {kb_id}: {e}")
                raise


# 全局实例
unified_kb_db_manager = KnowledgeBaseDBManager()
