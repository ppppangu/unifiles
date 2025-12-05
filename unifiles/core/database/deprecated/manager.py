"""
数据库管理器
提供统一的数据库操作接口，包含用户、知识库、文档、文件的CRUD操作
"""

import json
from typing import Any, Dict, Optional

import asyncpg

from unifiles.core.logging import get_logger

logger = get_logger()

from unifiles.core.config.env_config import read_pg_config

from ..models import (
    ChunkModel,
    DocumentModel,
    FileModel,
    FileProcessingLogModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingStatus,
    UserModel,
)


class DatabaseManager:
    """数据库管理器 - 提供统一的数据库操作接口"""

    def __init__(self):
        self.pg_config = read_pg_config()
        self._pool = None

    async def get_connection(self) -> asyncpg.Connection:
        """获取数据库连接"""
        # Filter out 'address' and 'active' keys - asyncpg only wants host, port, user, password, database
        conn_params = {
            k: v
            for k, v in self.pg_config.items()
            if k in ["host", "port", "user", "password", "database"]
        }
        return await asyncpg.connect(**conn_params)

    async def create_pool(self) -> asyncpg.Pool:
        """创建连接池"""
        if self._pool is None:
            # Filter out 'address' and 'active' keys - asyncpg only wants host, port, user, password, database
            conn_params = {
                k: v
                for k, v in self.pg_config.items()
                if k in ["host", "port", "user", "password", "database"]
            }
            self._pool = await asyncpg.create_pool(**conn_params)
        return self._pool

    async def close_pool(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ==================== 用户操作 ====================

    async def create_user(self, user_model: UserModel) -> UserModel:
        """创建用户"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO unifiles.users (id, knowledge_ids)
                    VALUES ($1, $2)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user_model.id,
                    json.dumps(user_model.knowledge_ids),
                )

                # 获取创建的用户信息
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.users WHERE id = $1", user_model.id
                )

                if result:
                    user_model.created_at = result["created_at"]

                logger.info(f"User created: {user_model.id}")
                return user_model

        except Exception as e:
            logger.error(f"Error creating user {user_model.id}: {e}")
            raise
        finally:
            await conn.close()

    async def get_user(self, user_id: str) -> Optional[UserModel]:
        """获取用户信息"""
        conn = await self.get_connection()
        try:
            result = await conn.fetchrow(
                "SELECT * FROM unifiles.users WHERE id = $1", user_id
            )

            if result:
                return UserModel(
                    id=result["id"],
                    knowledge_ids=json.loads(result["knowledge_ids"] or "[]"),
                    created_at=result["created_at"],
                )
            return None

        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise
        finally:
            await conn.close()

    async def ensure_user_exists(self, user_id: str) -> UserModel:
        """确保用户存在，不存在则创建"""
        user = await self.get_user(user_id)
        if not user:
            user = UserModel(id=user_id)
            user = await self.create_user(user)
        return user

    # ==================== 知识库操作 ====================

    async def create_knowledge_base(
        self, kb_model: KnowledgeBaseModel
    ) -> KnowledgeBaseModel:
        """创建知识库"""
        conn = await self.get_connection()
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
                    json.dumps(kb_model.document_ids),
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
        finally:
            await conn.close()

    async def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBaseModel]:
        """获取知识库信息"""
        conn = await self.get_connection()
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
        finally:
            await conn.close()

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
        """创建文档"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO unifiles.documents
                    (id, knowledge_base_id, name, text, component_ids, hierarchy_path, markdown_public_url, raw_file_public_url)
                    VALUES ($1, $2, $3, $4, $5, $6::ltree, $7, $8)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    doc_model.id,
                    doc_model.knowledge_base_id,
                    doc_model.name,
                    doc_model.text,
                    json.dumps(doc_model.component_ids),
                    doc_model.hierarchy_path,
                    doc_model.markdown_public_url,
                    doc_model.raw_file_public_url,
                )

                # 获取创建的文档信息
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.documents WHERE id = $1", doc_model.id
                )

                if result:
                    doc_model.created_at = result["created_at"]
                    doc_model.updated_at = result["updated_at"]
                    doc_model.upload_time = result.get("upload_time")

                logger.info(f"Document created: {doc_model.id}")
                return doc_model

        except Exception as e:
            logger.error(f"Error creating document {doc_model.id}: {e}")
            raise
        finally:
            await conn.close()

    async def get_document(self, doc_id: str) -> Optional[DocumentModel]:
        """获取文档信息"""
        conn = await self.get_connection()
        try:
            result = await conn.fetchrow(
                "SELECT * FROM unifiles.documents WHERE id = $1", doc_id
            )

            if result:
                return DocumentModel(
                    id=result["id"],
                    knowledge_base_id=result["knowledge_base_id"],
                    name=result["name"],
                    text=result["text"] or "",
                    component_ids=json.loads(result["component_ids"] or "[]"),
                    hierarchy_path=str(result["hierarchy_path"]),
                    markdown_public_url=result.get("markdown_public_url"),
                    raw_file_public_url=result.get("raw_file_public_url"),
                    upload_time=result.get("upload_time"),
                    created_at=result["created_at"],
                    updated_at=result["updated_at"],
                )
            return None

        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            raise
        finally:
            await conn.close()

    async def ensure_document_exists(
        self, doc_id: str, kb_id: str, name: Optional[str] = None
    ) -> DocumentModel:
        """确保文档存在，不存在则创建"""
        doc = await self.get_document(doc_id)
        if not doc:
            doc = DocumentModel(
                id=doc_id, knowledge_base_id=kb_id, name=name or f"Document {doc_id}"
            )
            doc = await self.create_document(doc)
        return doc

    async def update_document_urls(
        self, doc_id: str, markdown_url: str, raw_file_url: str
    ) -> bool:
        """更新文档URL信息"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE unifiles.documents
                    SET markdown_public_url = $2, raw_file_public_url = $3, upload_time = now()
                    WHERE id = $1
                    """,
                    doc_id,
                    markdown_url,
                    raw_file_url,
                )

                logger.info(f"Document URLs updated: {doc_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating document URLs {doc_id}: {e}")
            raise
        finally:
            await conn.close()

    # ==================== 文件操作 ====================

    async def create_file_record(self, file_model: FileModel) -> FileModel:
        """创建文件记录"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO unifiles.files
                    (id, user_id, bytes, filename, mime_type, file_path, raw_file_public_url, status, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    file_model.id,
                    file_model.user_id,
                    file_model.bytes,
                    file_model.filename,
                    file_model.mime_type,
                    file_model.file_path,
                    file_model.raw_file_public_url,
                    file_model.status.value,
                    json.dumps(file_model.metadata),
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
        finally:
            await conn.close()

    async def get_file_record(self, file_id: str) -> Optional[FileModel]:
        """获取文件记录"""
        conn = await self.get_connection()
        try:
            result = await conn.fetchrow(
                "SELECT * FROM unifiles.files WHERE id = $1", file_id
            )

            if result:
                return FileModel(
                    id=result["id"],
                    user_id=result["user_id"],
                    filename=result["filename"],
                    bytes=result["bytes"],
                    object_type=result.get("object", "file"),
                    purpose=result.get("purpose", "assistants"),
                    status=FileStatus(result["status"]),
                    status_details=result.get("status_details"),
                    mime_type=result.get("mime_type"),
                    file_path=result.get("file_path"),
                    raw_file_public_url=result.get("raw_file_public_url"),
                    processed_file_url=result.get("processed_file_url"),
                    metadata=json.loads(result.get("metadata") or "{}"),
                    created_at=result["created_at"],
                )
            return None

        except Exception as e:
            logger.error(f"Error getting file record {file_id}: {e}")
            raise
        finally:
            await conn.close()

    # ==================== 文本块操作 ====================

    async def save_chunk(self, chunk_model: ChunkModel) -> ChunkModel:
        """保存文本块"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                # 处理embedding向量格式
                embedding_vector = None
                if chunk_model.embedding is not None:
                    embedding_vector = f"[{','.join(map(str, chunk_model.embedding))}]"

                result = await conn.fetchrow(
                    """
                    INSERT INTO unifiles.chunks (id, document_id, doc_position, text, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    RETURNING id, doc_position, created_at, updated_at
                    """,
                    chunk_model.id,
                    chunk_model.document_id,
                    chunk_model.doc_position,
                    chunk_model.text,
                    embedding_vector,
                )

                chunk_model.doc_position = result["doc_position"]
                chunk_model.created_at = result["created_at"]
                chunk_model.updated_at = result["updated_at"]

                logger.info(
                    f"Chunk saved: {chunk_model.id} at position {chunk_model.doc_position}"
                )
                return chunk_model

        except Exception as e:
            logger.error(f"Error saving chunk {chunk_model.id}: {e}")
            raise
        finally:
            await conn.close()

    # ==================== 图片操作 ====================

    async def save_photo(self, photo_model: PhotoModel) -> PhotoModel:
        """保存图片"""
        conn = await self.get_connection()
        try:
            async with conn.transaction():
                # 处理embedding向量格式
                embedding_vector = None
                if photo_model.embedding is not None:
                    embedding_vector = f"[{','.join(map(str, photo_model.embedding))}]"

                result = await conn.fetchrow(
                    """
                    INSERT INTO unifiles.photos (id, document_id, type, text, base64_image, embedding, doc_position)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
                    RETURNING id, doc_position, created_at, updated_at
                    """,
                    photo_model.id,
                    photo_model.document_id,
                    photo_model.type,
                    photo_model.text,
                    photo_model.base64_image,
                    embedding_vector,
                    photo_model.doc_position,
                )

                photo_model.doc_position = result["doc_position"]
                photo_model.created_at = result["created_at"]
                photo_model.updated_at = result["updated_at"]

                logger.info(
                    f"Photo saved: {photo_model.id} at position {photo_model.doc_position}"
                )
                return photo_model

        except Exception as e:
            logger.error(f"Error saving photo {photo_model.id}: {e}")
            raise
        finally:
            await conn.close()

    # ==================== 处理日志操作 ====================

    async def create_processing_log(
        self, log_model: FileProcessingLogModel
    ) -> FileProcessingLogModel:
        """创建处理日志"""
        conn = await self.get_connection()
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
        finally:
            await conn.close()

    async def update_processing_log(
        self,
        log_id: str,
        status: ProcessingStatus,
        message: Optional[str] = None,
        error_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新处理日志状态"""
        conn = await self.get_connection()
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
        finally:
            await conn.close()
