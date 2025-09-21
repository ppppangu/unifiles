"""
存储服务适配器
为document_processor提供兼容的存储服务接口
保留原有的业务逻辑功能
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..storage import get_storage, Storage
from ..database.manager import DatabaseManager
from ..database.models import ChunkModel, PhotoModel


class VectorStorageManager:
    """向量数据库存储管理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config
        self.db_manager = DatabaseManager()

    async def save_text_chunk(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        doc_position: int,
        embedding: List[float],
    ) -> ChunkModel:
        """保存文本块到向量数据库"""
        try:
            chunk_model = ChunkModel(
                id=chunk_id,
                document_id=document_id,
                text=text,
                doc_position=doc_position,
                embedding=embedding,
            )

            return await self.db_manager.save_chunk(chunk_model)

        except Exception as e:
            logger.error(f"Failed to save text chunk: {e}")
            raise

    async def save_image_data(
        self,
        photo_id: str,
        document_id: str,
        image_text: str,
        doc_position: int,
        embedding: List[float],
        photo_type: str = "photo",
        base64_image: Optional[str] = None,
    ) -> PhotoModel:
        """保存图片数据到向量数据库"""
        try:
            photo_model = PhotoModel(
                id=photo_id,
                document_id=document_id,
                type=photo_type,
                text=image_text,
                base64_image=base64_image,
                embedding=embedding,
                doc_position=doc_position,
            )

            return await self.db_manager.save_photo(photo_model)

        except Exception as e:
            logger.error(f"Failed to save image data: {e}")
            raise

    async def batch_save_structured_content(
        self,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        document_name: str,
        content_list: List[Dict[str, Any]],
    ) -> List[str]:
        """批量保存结构化内容到向量数据库"""
        try:
            # 确保用户、知识库、文档存在
            await self.db_manager.ensure_user_exists(user_id)
            await self.db_manager.ensure_knowledge_base_exists(
                knowledge_base_id, user_id, f"Knowledge Base {knowledge_base_id}"
            )
            await self.db_manager.ensure_document_exists(
                document_id, knowledge_base_id, document_name
            )

            # 批量保存内容
            saved_ids = []
            save_tasks = []

            for item in content_list:
                component_id = str(uuid.uuid4())

                if item["type"] == "text":
                    task = self.save_text_chunk(
                        chunk_id=component_id,
                        document_id=document_id,
                        text=item["content"],
                        doc_position=item["index"],
                        embedding=item["embedding"],
                    )
                elif item["type"] == "image":
                    task = self.save_image_data(
                        photo_id=component_id,
                        document_id=document_id,
                        image_text=item["content"],
                        doc_position=item["index"],
                        embedding=item["embedding"],
                        photo_type="photo",
                    )
                else:
                    logger.warning(f"Unknown content type: {item['type']}")
                    continue

                save_tasks.append(task)
                saved_ids.append(component_id)

            # 并发执行保存任务
            await asyncio.gather(*save_tasks)

            logger.info(
                f"Batch saved {len(saved_ids)} structured content items to vector database"
            )
            return saved_ids

        except Exception as e:
            logger.error(f"Failed to batch save structured content: {e}")
            raise


class StorageService:
    """存储服务适配器 - 为document_processor提供兼容接口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config
        self.storage = get_storage()
        self.vector_manager = VectorStorageManager(config)
        self.db_manager = DatabaseManager()

    async def store_processed_files(
        self,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        markdown_content: str,
        pdf_file_path: str,
        original_filename: str,
    ) -> Dict[str, str]:
        """存储处理后的文件（Markdown和PDF）"""
        try:
            # 获取存储后端
            backend = await self.storage.get_default_backend()
            
            # 构建对象路径
            md_object_path = f"{user_id}/knowledgebase/{knowledge_base_id}/{document_id}/{document_id}.md"
            pdf_object_path = f"{user_id}/knowledgebase/{knowledge_base_id}/{document_id}/{document_id}.pdf"

            # 上传Markdown文件
            md_content_bytes = markdown_content.encode("utf-8")
            md_url = await backend.upload_file(
                object_path=md_object_path,
                content=md_content_bytes,
                content_type="text/markdown",
            )

            # 上传PDF文件
            pdf_url = await backend.upload_file_from_path(
                object_path=pdf_object_path,
                local_file_path=pdf_file_path,
                content_type="application/pdf",
            )

            # 更新文档的URL信息
            await self.db_manager.update_document_urls(document_id, md_url, pdf_url)

            logger.info(
                f"Processed files stored successfully - MD: {md_url}, PDF: {pdf_url}"
            )

            return {"markdown_public_url": md_url, "pdf_file_public_url": pdf_url}

        except Exception as e:
            logger.error(f"Failed to store processed files: {e}")
            raise

    async def store_structured_content_to_vector_db(
        self,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        document_name: str,
        structured_content: List[Dict[str, Any]],
    ) -> List[str]:
        """将结构化内容存储到向量数据库"""
        return await self.vector_manager.batch_save_structured_content(
            user_id, knowledge_base_id, document_id, document_name, structured_content
        )

    async def save_processing_results(
        self,
        user_id: str,
        knowledge_base_id: str,
        document_id: str,
        document_name: str,
        markdown_content: str,
        pdf_file_path: str,
        structured_content: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """保存完整的处理结果"""
        try:
            logger.info("=== Stage 5: Saving processing results ===")

            # 并发执行存储任务
            store_files_task = self.store_processed_files(
                user_id,
                knowledge_base_id,
                document_id,
                markdown_content,
                pdf_file_path,
                document_name,
            )

            store_vector_task = self.store_structured_content_to_vector_db(
                user_id,
                knowledge_base_id,
                document_id,
                document_name,
                structured_content,
            )

            # 等待所有任务完成
            file_urls, component_ids = await asyncio.gather(
                store_files_task, store_vector_task
            )

            result = {
                "file_uuid": document_id,
                "markdown_public_url": file_urls["markdown_public_url"],
                "pdf_file_public_url": file_urls["pdf_file_public_url"],
                "component_count": len(component_ids),
                "component_ids": component_ids,
            }

            logger.info(
                f"Processing results saved successfully: {len(structured_content)} components stored"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to save processing results: {e}")
            raise

    async def cleanup_temporary_files(self, *file_paths: str):
        """清理临时文件"""
        cleanup_tasks = []
        for file_path in file_paths:
            if file_path and Path(file_path).exists():
                cleanup_tasks.append(
                    asyncio.to_thread(Path(file_path).unlink, missing_ok=True)
                )

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)
            logger.info(f"Cleaned up {len(cleanup_tasks)} temporary files")

    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        try:
            health = await self.storage.health_check()
            return {
                "storage_status": health.get("status", "unknown"),
                "database_type": "postgresql_with_pgvector",
                "supported_file_types": ["markdown", "pdf", "json"],
            }
        except Exception as e:
            logger.error(f"Failed to get service info: {e}")
            return {
                "storage_status": "error",
                "database_type": "postgresql_with_pgvector",
                "supported_file_types": ["markdown", "pdf", "json"],
            }