import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, UploadFile
from loguru import logger

from unifiles.app.schemas import FileInfo, FileListResponse, FileUploadResponse
from unifiles.core.database.base import FileDBManager
from unifiles.core.security.authorization import FileAccessControl
from unifiles.core.security.validators import FileSecurityValidator
from unifiles.core.storage import Storage, get_storage


class FileService:
    """文件管理业务逻辑服务"""

    def __init__(self, storage: Optional[Storage] = None, db_manager: Optional[FileDBManager] = None):
        """
        初始化文件服务

        Args:
            storage: 存储实例，如果为None则使用默认实例
            db_manager: 数据库管理器
        """
        self.storage = storage or get_storage()
        self.db = db_manager
        self.validator = FileSecurityValidator()
        self.access_control = FileAccessControl()
        self._current_backend = None

    async def upload_file(
        self,
        user_id: str,
        file: UploadFile,
        is_public: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileUploadResponse:
        """
        上传文件的完整业务逻辑

        Args:
            user_id: 用户ID
            file: 上传的文件
            is_public: 是否公开
            metadata: 额外元数据

        Returns:
            文件上传响应

        Raises:
            HTTPException: 上传失败时抛出
        """
        try:
            # 1. 基础验证
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")

            # 2. 读取文件内容
            file_content = await file.read()
            if len(file_content) == 0:
                raise HTTPException(status_code=400, detail="Empty file provided")

            # 3. 安全验证
            validation_result = self.validator.validate_upload_file(
                file_content, file.filename
            )
            if not validation_result["valid"]:
                error_msg = "; ".join(validation_result["errors"])
                raise HTTPException(
                    status_code=400, detail=f"File validation failed: {error_msg}"
                )

            # 4. 生成安全的文件信息
            file_id = f"file-{uuid.uuid4()!s}"
            sanitized_filename = validation_result["sanitized_filename"]
            detected_mime_type = validation_result["detected_mime_type"]
            file_size = validation_result["file_size"]

            # 5. 生成安全的存储路径
            object_path = FileSecurityValidator.generate_secure_path(
                user_id, file_id, sanitized_filename
            )

            # 6. 准备文件元数据
            file_metadata = {
                "original_filename": file.filename,
                "sanitized_filename": sanitized_filename,
                "uploaded_by": user_id,
                "upload_timestamp": datetime.now().isoformat(),
                "file_id": file_id,
                "is_public": is_public,
            }

            if metadata:
                file_metadata.update(metadata)

            # 7. 获取存储后端并上传文件
            storage_backend = await self.storage.get_default_backend()
            storage_path = await storage_backend.upload_file(
                object_path=object_path,
                content=file_content,
                content_type=detected_mime_type,
                metadata=file_metadata,
            )

            # 8. 记录到数据库
            await self.db.add_file_record(
                file_id=file_id,
                user_id=user_id,
                filename=sanitized_filename,
                file_size=file_size,
                content_type=detected_mime_type,
                storage_path=storage_path,
                storage_config_id="minio-default",  # 可以从配置中获取
            )

            # 9. 设置公开状态（如果需要）
            if is_public:
                await self.db.update_file_public_status(file_id, True)

            # 10. 生成访问URL
            access_type = "public" if is_public else "presigned"
            public_url = storage_backend.get_access_url(
                object_path=storage_path,
                access_type=access_type,
                expires_in_hours=24 if not is_public else None,
            )

            # 11. 构建返回信息
            file_info = FileInfo(
                file_id=file_id,
                filename=sanitized_filename,
                file_size=file_size,
                content_type=detected_mime_type,
                public_url=public_url,
                object_path=storage_path,
                is_public=is_public,
                created_at=datetime.now().isoformat(),
            )

            logger.info(f"File uploaded successfully: {file_id} by user: {user_id}")

            return FileUploadResponse(
                success=True, message="File uploaded successfully", file=file_info
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in file upload service: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {e!s}")

    async def get_user_files(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> FileListResponse:
        """
        获取用户文件列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            文件列表响应
        """
        try:
            # 验证参数
            if limit < 1 or limit > 100:
                raise HTTPException(
                    status_code=400, detail="Limit must be between 1 and 100"
                )
            if offset < 0:
                raise HTTPException(
                    status_code=400, detail="Offset must be non-negative"
                )

            # 从数据库获取文件记录
            file_records = await self.db.get_user_files(user_id, limit, offset)

            files = []
            for record in file_records:
                try:
                    # 重新生成访问URL以确保是最新的
                    is_public = record.get("is_public", False)
                    access_type = "public" if is_public else "presigned"

                    # 获取存储后端（可能需要根据文件的storage_config_id获取特定后端）
                    storage_backend = await self._get_storage_backend_for_file(record)
                    fresh_url = storage_backend.get_access_url(
                        object_path=record["storage_path"],
                        access_type=access_type,
                        expires_in_hours=24 if not is_public else None,
                    )

                    file_info = FileInfo(
                        file_id=record["id"],
                        filename=record["filename"],
                        file_size=record["bytes"],
                        content_type=record["mime_type"],
                        public_url=fresh_url,
                        object_path=record["storage_path"],
                        is_public=is_public,
                        created_at=record["created_at"].isoformat(),
                    )
                    files.append(file_info)

                except Exception as e:
                    logger.warning(
                        f"Error processing file record {record.get('id')}: {e}"
                    )
                    # 继续处理其他文件，不中断整个列表
                    continue

            # 检查是否还有更多文件
            has_more = len(file_records) == limit

            logger.info(f"Retrieved {len(files)} files for user: {user_id}")

            return FileListResponse(
                success=True,
                message="Files retrieved successfully",
                files=files,
                total_count=None,  # 可以添加总数查询
                has_more=has_more,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user files: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get files: {e!s}")

    async def get_file_info(self, user_id: str, file_id: str) -> FileInfo:
        """
        获取文件信息

        Args:
            user_id: 用户ID
            file_id: 文件ID

        Returns:
            文件信息
        """
        try:
            # 验证访问权限
            file_record = await self.access_control.verify_file_access(
                user_id, file_id, "read"
            )

            # 生成最新的访问URL
            is_public = file_record.get("is_public", False)
            access_type = "public" if is_public else "presigned"

            storage_backend = await self._get_storage_backend_for_file(file_record)
            fresh_url = storage_backend.get_access_url(
                object_path=file_record["storage_path"],
                access_type=access_type,
                expires_in_hours=24 if not is_public else None,
            )

            return FileInfo(
                file_id=file_record["id"],
                filename=file_record["filename"],
                file_size=file_record["bytes"],
                content_type=file_record["mime_type"],
                public_url=fresh_url,
                object_path=file_record["storage_path"],
                is_public=is_public,
                created_at=file_record["created_at"].isoformat(),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting file info for {file_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get file info: {e!s}"
            )

    async def update_file_public_status(
        self, user_id: str, file_id: str, is_public: bool
    ) -> Dict[str, Any]:
        """
        更新文件公开状态

        Args:
            user_id: 用户ID
            file_id: 文件ID
            is_public: 是否公开

        Returns:
            更新结果
        """
        try:
            # 验证访问权限
            await self.access_control.verify_file_access(user_id, file_id, "update")

            # 更新数据库中的公开状态
            await self.db.update_file_public_status(file_id, is_public)

            logger.info(
                f"File {file_id} public status updated to {is_public} by user {user_id}"
            )

            return {
                "file_id": file_id,
                "is_public": is_public,
                "updated_at": datetime.now().isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating file public status: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update file public status: {e!s}"
            )

    async def delete_file(self, user_id: str, file_id: str) -> Dict[str, Any]:
        """
        删除文件

        Args:
            user_id: 用户ID
            file_id: 文件ID

        Returns:
            删除结果
        """
        try:
            # 验证访问权限
            file_record = await self.access_control.verify_file_access(
                user_id, file_id, "delete"
            )

            # 从存储后端删除文件
            storage_backend = await self._get_storage_backend_for_file(file_record)
            storage_deleted = await storage_backend.delete_file(
                file_record["storage_path"]
            )
            if not storage_deleted:
                logger.warning(
                    f"Storage deletion failed for file {file_id}, continuing with DB cleanup"
                )

            # 从数据库删除记录
            await self.db.delete_file_record(file_id)

            logger.info(f"File {file_id} deleted successfully by user {user_id}")

            return {
                "file_id": file_id,
                "deleted_at": datetime.now().isoformat(),
                "storage_deleted": storage_deleted,
            }

        except HTTPException as e:
            if e.status_code == 404:
                # 文件不存在，视为删除成功（幂等性）
                logger.info(f"Delete request for non-existent file: {file_id}")
                return {
                    "file_id": file_id,
                    "message": "File already deleted or never existed",
                    "deleted_at": datetime.now().isoformat(),
                }
            raise
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {e!s}")

    async def get_public_file_info(self, file_id: str) -> FileInfo:
        """
        获取公共文件信息（无需认证）

        Args:
            file_id: 文件ID

        Returns:
            文件信息
        """
        try:
            # 验证公共访问权限
            file_record = await self.access_control.verify_public_file_access(file_id)

            # 生成公共访问URL
            storage_backend = await self._get_storage_backend_for_file(file_record)
            public_url = storage_backend.get_access_url(
                object_path=file_record["storage_path"], access_type="public"
            )

            return FileInfo(
                file_id=file_record["id"],
                filename=file_record["filename"],
                file_size=file_record["bytes"],
                content_type=file_record["mime_type"],
                public_url=public_url,
                object_path=file_record["storage_path"],
                is_public=True,
                created_at=file_record["created_at"].isoformat(),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting public file info for {file_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get public file info: {e!s}"
            )

    async def get_storage_health(self) -> Dict[str, Any]:
        """
        获取存储后端健康状态

        Returns:
            健康状态信息
        """
        try:
            # 使用Storage的健康检查
            return await self.storage.health_check()
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Storage backend is not accessible",
            }

    async def get_storage_metrics(self) -> Dict[str, Any]:
        """
        获取存储指标

        Returns:
            存储指标信息
        """
        try:
            # 获取默认存储后端的指标
            storage_backend = await self.storage.get_default_backend()
            if hasattr(storage_backend, "get_metrics"):
                return storage_backend.get_metrics()
            return {
                "storage_type": storage_backend.get_storage_type(),
                "message": "Metrics not available for this storage backend",
            }
        except Exception as e:
            logger.error(f"Failed to get storage metrics: {e}")
            return {"error": str(e), "message": "Failed to retrieve storage metrics"}

    async def _get_storage_backend_for_file(self, file_record: Dict[str, Any]):
        """
        根据文件记录获取对应的存储后端
        
        Args:
            file_record: 文件记录
            
        Returns:
            存储后端实例
        """
        try:
            # 尝试从文件记录中获取storage_config_id
            storage_config_id = file_record.get("storage_config_id")
            if storage_config_id:
                return await self.storage.get_backend(storage_config_id)
            # 使用默认存储后端
            return await self.storage.get_default_backend()
        except Exception as e:
            logger.warning(f"Failed to get specific storage backend, using default: {e}")
            return await self.storage.get_default_backend()
