"""
存储服务
提供MinIO对象存储和向量数据库的统一存储接口
"""

import asyncio
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
from loguru import logger
from minio import Minio

from ..database.manager import DatabaseManager
from ..database.models import ChunkModel, DocumentModel, PhotoModel
from ..utils.tools import detect_content_type, read_config, read_minio_config


class MinIOStorageManager:
    """MinIO存储管理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.minio_config = read_minio_config()
        self._client = None

    def _get_client(self) -> Minio:
        """获取MinIO客户端"""
        if self._client is None:
            # 处理address格式或host:port格式
            if "address" in self.minio_config:
                endpoint = self.minio_config["address"]
            else:
                endpoint = f"{self.minio_config['host']}:{self.minio_config['port']}"

            self._client = Minio(
                endpoint,
                access_key=self.minio_config["access_key"],
                secret_key=self.minio_config["secret_key"],
                secure=self.minio_config.get("secure", False),
                region=self.minio_config.get("region"),
            )

            # 确保bucket存在
            bucket_name = self.minio_config["bucket_name"]
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info(f"Created MinIO bucket: {bucket_name}")

        return self._client

    def generate_public_url(self, object_path: str) -> str:
        """生成对象的公网访问URL"""
        bucket_name = self.minio_config["bucket_name"]

        if self.minio_config.get("use_public_url", False) and self.minio_config.get(
            "public_url_prefix"
        ):
            return (
                f"{self.minio_config['public_url_prefix']}/{bucket_name}/{object_path}"
            )
        else:
            # 使用内网地址
            if "address" in self.minio_config:
                return (
                    f"http://{self.minio_config['address']}/{bucket_name}/{object_path}"
                )
            else:
                return f"http://{self.minio_config['host']}:{self.minio_config['port']}/{bucket_name}/{object_path}"

    async def upload_file(
        self, object_path: str, file_content: bytes, content_type: str = None
    ) -> str:
        """
        上传文件到MinIO

        Args:
            object_path: 对象路径
            file_content: 文件内容
            content_type: 内容类型

        Returns:
            公网访问URL
        """
        try:
            client = self._get_client()
            bucket_name = self.minio_config["bucket_name"]

            # 检测内容类型
            if not content_type:
                filename = object_path.split("/")[-1]
                content_type = detect_content_type(filename)

            # 上传文件
            await asyncio.to_thread(
                client.put_object,
                bucket_name,
                object_path,
                io.BytesIO(file_content),
                len(file_content),
                content_type,
                part_size=10 * 1024 * 1024,  # 10MB分片
            )

            public_url = self.generate_public_url(object_path)
            logger.info(f"File uploaded to MinIO: {object_path}, URL: {public_url}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload file to MinIO: {e}")
            raise

    async def upload_file_from_path(
        self, object_path: str, local_file_path: str, content_type: str = None
    ) -> str:
        """
        从本地文件路径上传到MinIO

        Args:
            object_path: 对象路径
            local_file_path: 本地文件路径
            content_type: 内容类型

        Returns:
            公网访问URL
        """
        try:
            client = self._get_client()
            bucket_name = self.minio_config["bucket_name"]

            # 检测内容类型
            if not content_type:
                filename = Path(local_file_path).name
                content_type = detect_content_type(filename)

            # 上传文件
            await asyncio.to_thread(
                client.fput_object,
                bucket_name,
                object_path,
                local_file_path,
                content_type,
            )

            public_url = self.generate_public_url(object_path)
            logger.info(
                f"File uploaded from path to MinIO: {local_file_path} -> {object_path}, URL: {public_url}"
            )

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload file from path to MinIO: {e}")
            raise

    async def delete_object(self, object_path: str) -> bool:
        """删除对象"""
        try:
            client = self._get_client()
            bucket_name = self.minio_config["bucket_name"]

            await asyncio.to_thread(client.remove_object, bucket_name, object_path)
            logger.info(f"Object deleted from MinIO: {object_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete object from MinIO: {e}")
            return False


class VectorStorageManager:
    """向量数据库存储管理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
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
        base64_image: str = None,
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
        """
        批量保存结构化内容到向量数据库

        Args:
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            document_id: 文档ID
            document_name: 文档名称
            content_list: 结构化内容列表

        Returns:
            保存的组件ID列表
        """
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
                    # 从图片markdown中提取URL
                    import re

                    pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
                    match = re.search(pattern, item["content"])
                    photo_url = match.group(2) if match else ""

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
    """存储服务主类 - 统一的存储接口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.minio_manager = MinIOStorageManager(config)
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
        """
        存储处理后的文件（Markdown和PDF）

        Args:
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            document_id: 文档ID
            markdown_content: Markdown内容
            pdf_file_path: PDF文件本地路径
            original_filename: 原始文件名

        Returns:
            包含URL的字典
        """
        try:
            # 构建对象路径
            md_object_path = f"{user_id}/knowledgebase/{knowledge_base_id}/{document_id}/{document_id}.md"
            pdf_object_path = f"{user_id}/knowledgebase/{knowledge_base_id}/{document_id}/{document_id}.pdf"

            # 上传Markdown文件
            md_content_bytes = markdown_content.encode("utf-8")
            md_url = await self.minio_manager.upload_file(
                object_path=md_object_path,
                file_content=md_content_bytes,
                content_type="text/markdown",
            )

            # 上传PDF文件
            pdf_url = await self.minio_manager.upload_file_from_path(
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
        """
        保存完整的处理结果

        Args:
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            document_id: 文档ID
            document_name: 文档名称
            markdown_content: Markdown内容
            pdf_file_path: PDF文件本地路径
            structured_content: 结构化内容列表

        Returns:
            包含所有保存结果的字典
        """
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

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "minio_endpoint": self.minio_manager.minio_config.get("address")
            or f"{self.minio_manager.minio_config['host']}:{self.minio_manager.minio_config['port']}",
            "minio_bucket": self.minio_manager.minio_config["bucket_name"],
            "database_type": "postgresql_with_pgvector",
            "supported_file_types": ["markdown", "pdf", "json"],
        }


# 默认存储服务实例
_default_storage_service: Optional[StorageService] = None


def get_storage_service(config: Optional[Dict[str, Any]] = None) -> StorageService:
    """获取默认存储服务实例（单例模式）"""
    global _default_storage_service
    if _default_storage_service is None:
        _default_storage_service = StorageService(config=config)
    return _default_storage_service
