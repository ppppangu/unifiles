import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, UploadFile
from unifiles.core.logging import get_logger

from unifiles.app.schemas import FileInfo, FileListResponse, FileUploadResponse
from unifiles.core.database.base import FileDBManager
from unifiles.core.database.manager import DatabaseManager
from unifiles.core.database.models import (
    FileProcessingLogModel,
    ProcessingStage,
    ProcessingStatus,
)
from unifiles.core.pipelines.format_validator import FileFormatValidator, PDFConverter
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
        self.db = db_manager  # 文件记录管理
        self.db_manager = DatabaseManager()  # 处理日志管理
        self.validator = FileSecurityValidator()
        self.access_control = FileAccessControl()
        self._current_backend = None
        # 初始化PDF转换器
        self.pdf_converter = PDFConverter()
        self.format_validator = FileFormatValidator()
        # 使用应用统一日志（带 service 过滤），避免被全局 Loguru 过滤掉
        global logger
        logger = get_logger()

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
            logger.info(f"File content read: {len(file_content)} bytes")
            if len(file_content) == 0:
                raise HTTPException(status_code=400, detail="Empty file provided")

            # 3. 安全验证
            import sys
            print(f"DEBUG SERVICE: About to call validator", file=sys.stderr)
            sys.stderr.flush()

            logger.info(f"Validating file: {file.filename}")
            validation_result = self.validator.validate_upload_file(
                file_content, file.filename
            )

            print(f"DEBUG SERVICE: Received validation_result", file=sys.stderr)
            print(f"DEBUG SERVICE: type = {type(validation_result)}", file=sys.stderr)
            print(f"DEBUG SERVICE: value = {validation_result}", file=sys.stderr)
            sys.stderr.flush()

            logger.info(f"Validation result type: {type(validation_result)}")
            logger.info(f"Validation result: {validation_result}")

            # 调试：打印validation_result的所有key
            if isinstance(validation_result, dict):
                logger.info(f"Validation result keys: {list(validation_result.keys())}")
                for key, value in validation_result.items():
                    logger.info(f"  {key} = {value} (type: {type(value).__name__})")

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

            # 处理日志：仅生成ID，占位，待文件记录写入后再创建，避免外键错误
            log_id = f"log-{uuid.uuid4()!s}"
            log_created = False

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

            # 7. PDF转换处理（在上传之前）
            # 先临时上传文件以获取URL，供转换服务使用
            logger.info("=" * 80)
            logger.info("[FILE UPLOAD] Step 7: Starting PDF conversion workflow")
            logger.info(f"[FILE UPLOAD] Getting storage backend...")
            storage_backend = await self.storage.get_default_backend()
            logger.info(f"[FILE UPLOAD] ✓ Storage backend obtained")

            logger.info(f"[FILE UPLOAD] Uploading temporary file to storage...")
            logger.info(f"[FILE UPLOAD] Object path: {object_path}")
            temp_storage_path = await storage_backend.upload_file(
                object_path=object_path,
                content=file_content,
                content_type=detected_mime_type,
                metadata=file_metadata,
            )
            logger.info(f"[FILE UPLOAD] ✓ Temporary file uploaded: {temp_storage_path}")

            # 生成临时访问URL - 使用 public 类型，因为 MinIO 配置为 public
            temp_public_url = storage_backend.get_access_url(
                object_path=temp_storage_path,
                access_type="public",
                expires_in_hours=None,  # public URL 不需要过期时间
            )

            logger.info("=" * 80)
            logger.info(f"[FILE UPLOAD] Temporary file uploaded for PDF conversion check")
            logger.info(f"[FILE UPLOAD] Temp storage path: {temp_storage_path}")
            logger.info(f"[FILE UPLOAD] Temp PUBLIC URL generated: {temp_public_url}")
            logger.info(f"[FILE UPLOAD] Checking if PDF conversion is needed for: {sanitized_filename}")
            logger.info("=" * 80)

            converted_info = await self._convert_to_pdf_if_needed(
                file_content=file_content,
                filename=sanitized_filename,
                public_url=temp_public_url,
            )

            # 如果转换成功，使用转换后的PDF文件
            if converted_info["converted"]:
                logger.info("=" * 80)
                logger.info(f"[FILE UPLOAD] ✅ PDF conversion successful!")
                logger.info(f"[FILE UPLOAD] Original file: {sanitized_filename}")
                logger.info(f"[FILE UPLOAD] Converted to: {converted_info['pdf_filename']}")
                logger.info(f"[FILE UPLOAD] Original size: {len(file_content)} bytes")
                logger.info(f"[FILE UPLOAD] PDF size: {len(converted_info['pdf_content'])} bytes")
                logger.info("=" * 80)

                # 更新文件内容、大小、类型
                file_content = converted_info["pdf_content"]
                file_size = len(file_content)
                detected_mime_type = "application/pdf"
                original_filename = sanitized_filename
                sanitized_filename = converted_info["pdf_filename"]

                # 重新生成存储路径（使用PDF文件名）
                object_path = FileSecurityValidator.generate_secure_path(
                    user_id, file_id, sanitized_filename
                )

                # 更新元数据
                file_metadata["original_filename"] = original_filename
                file_metadata["sanitized_filename"] = sanitized_filename
                file_metadata["is_converted"] = True
                file_metadata["conversion_status"] = "success"

                # 删除临时文件
                logger.info(f"[FILE UPLOAD] Deleting temporary file: {temp_storage_path}")
                await storage_backend.delete_file(temp_storage_path)
            else:
                logger.info("=" * 80)
                logger.info(f"[FILE UPLOAD] Conversion status: {converted_info['status']}")
                logger.info(f"[FILE UPLOAD] Using original file: {sanitized_filename}")
                if "error" in converted_info:
                    logger.warning(f"[FILE UPLOAD] Conversion error: {converted_info['error']}")
                logger.info("=" * 80)

                # 不需要转换或转换失败，使用已上传的原文件
                storage_path = temp_storage_path
                file_metadata["is_converted"] = False
                file_metadata["conversion_status"] = converted_info["status"]
                # 跳到步骤9（数据库记录）

            # 8. 上传最终文件到存储（如果转换成功，这里上传的是PDF）
            if converted_info["converted"]:
                storage_path = await storage_backend.upload_file(
                    object_path=object_path,
                    content=file_content,
                    content_type=detected_mime_type,
                    metadata=file_metadata,
                )
                logger.info(f"Converted PDF uploaded: {storage_path}")

            # 9. 记录到数据库
            # 为避免外键不一致导致插入失败，这里不强制写入 storage_config_id，保持为 NULL
            storage_config_id = None

            await self.db.add_file_record(
                file_id=file_id,
                user_id=user_id,
                filename=sanitized_filename,
                file_size=file_size,
                content_type=detected_mime_type,
                storage_path=storage_path,
                storage_config_id=storage_config_id,
            )

            # 创建处理日志（此时 files 记录已存在，不会违反外键）
            processing_log = FileProcessingLogModel(
                id=log_id,
                file_id=file_id,
                stage=ProcessingStage.UPLOAD,
                status=ProcessingStatus.PENDING,
                message="File upload started",
            )
            await self.db_manager.create_processing_log(processing_log)
            log_created = True
            logger.info(
                f"[PROCESSING LOG] Created log {log_id} for file {file_id}: stage=upload, status=pending"
            )

            # 更新处理日志 - 上传完成
            await self.db_manager.update_processing_log(
                log_id=log_id,
                status=ProcessingStatus.COMPLETED,
                message=f"File uploaded successfully: {sanitized_filename}",
            )
            logger.info(f"[PROCESSING LOG] Updated log {log_id} to COMPLETED")

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
                # PDF转换相关字段
                original_filename=file_metadata.get("original_filename") if file_metadata.get("is_converted") else None,
                is_converted=file_metadata.get("is_converted", False),
                conversion_status=file_metadata.get("conversion_status"),
            )

            logger.info(f"File uploaded successfully: {file_id} by user: {user_id}")

            return FileUploadResponse(
                success=True, message="File uploaded successfully", file=file_info
            )

        except HTTPException:
            # 更新处理日志为失败（仅在已创建时）
            if 'log_id' in locals() and 'log_created' in locals() and log_created:
                try:
                    await self.db_manager.update_processing_log(
                        log_id=log_id,
                        status=ProcessingStatus.FAILED,
                        message="File upload failed (HTTP exception)",
                    )
                    logger.info(f"[PROCESSING LOG] Updated log {log_id} to FAILED")
                except Exception as log_error:
                    logger.error(f"Failed to update processing log: {log_error}")
            raise
        except Exception as e:
            # 更新处理日志为失败（仅在已创建时）
            if 'log_id' in locals() and 'log_created' in locals() and log_created:
                try:
                    await self.db_manager.update_processing_log(
                        log_id=log_id,
                        status=ProcessingStatus.FAILED,
                        message=f"Upload failed: {str(e)}",
                        error_info={"error": str(e), "type": type(e).__name__}
                    )
                    logger.info(f"[PROCESSING LOG] Updated log {log_id} to FAILED with error details")
                except Exception as log_error:
                    logger.error(f"Failed to update processing log: {log_error}")

            logger.error(f"Error in file upload service: {e}")
            logger.exception("Full traceback:")  # 打印完整堆栈
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

    async def _convert_to_pdf_if_needed(
        self, file_content: bytes, filename: str, public_url: str
    ) -> Dict[str, Any]:
        """
        如果需要，将文件转换为PDF

        Args:
            file_content: 文件内容
            filename: 文件名
            public_url: 文件的公共访问URL

        Returns:
            {
                "converted": bool,  # 是否进行了转换
                "pdf_content": Optional[bytes],  # PDF内容
                "pdf_filename": Optional[str],  # PDF文件名
                "status": str,  # "success" | "skipped" | "failed"
            }
        """
        logger.info("=" * 80)
        logger.info(f"[PDF CONVERSION] Starting PDF conversion check")
        logger.info(f"[PDF CONVERSION] Filename: {filename}")
        logger.info(f"[PDF CONVERSION] File size: {len(file_content)} bytes")
        logger.info(f"[PDF CONVERSION] Public URL: {public_url[:100]}..." if len(public_url) > 100 else f"[PDF CONVERSION] Public URL: {public_url}")

        try:
            # 1. 检查是否已经是PDF
            logger.info(f"[PDF CONVERSION] Step 1: Checking if file is already PDF")
            if filename.lower().endswith('.pdf'):
                logger.info(f"[PDF CONVERSION] ✓ File is already PDF, skipping conversion: {filename}")
                logger.info("=" * 80)
                return {
                    "converted": False,
                    "status": "skipped",
                }
            logger.info(f"[PDF CONVERSION] ✓ File is not PDF, continue checking")

            # 2. 检查是否为可转换的文档格式
            logger.info(f"[PDF CONVERSION] Step 2: Checking if file is a convertible document format")
            if not self.format_validator.is_document_file(filename):
                logger.info(f"[PDF CONVERSION] ✗ File is not a document format, skipping conversion: {filename}")
                logger.info("=" * 80)
                return {
                    "converted": False,
                    "status": "skipped",
                }
            logger.info(f"[PDF CONVERSION] ✓ File is a convertible document format")

            # 3. 调用转换服务
            logger.info(f"[PDF CONVERSION] Step 3: Calling PDF conversion service")
            logger.info(f"[PDF CONVERSION] Sending file URL to conversion service: {public_url}")

            pdf_url = await self.pdf_converter.convert_document_to_pdf(public_url)

            if not pdf_url:
                logger.error(f"[PDF CONVERSION] ✗ PDF conversion service returned empty result")
                logger.error(f"[PDF CONVERSION] Conversion FAILED for: {filename}")
                logger.info("=" * 80)
                return {
                    "converted": False,
                    "status": "failed",
                }

            logger.info(f"[PDF CONVERSION] ✓ Conversion service returned PDF URL: {pdf_url}")

            # 4. 下载转换后的PDF内容
            logger.info(f"[PDF CONVERSION] Step 4: Downloading converted PDF content")
            import httpx
            from pathlib import Path

            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"[PDF CONVERSION] Fetching PDF from: {pdf_url}")
                response = await client.get(pdf_url)
                response.raise_for_status()
                pdf_content = response.content
                logger.info(f"[PDF CONVERSION] ✓ Downloaded PDF content: {len(pdf_content)} bytes")

            # 5. 生成PDF文件名
            pdf_filename = Path(filename).stem + ".pdf"
            logger.info(f"[PDF CONVERSION] Generated PDF filename: {pdf_filename}")

            logger.info(f"[PDF CONVERSION] ✅ Successfully converted to PDF: {filename} -> {pdf_filename}")
            logger.info(f"[PDF CONVERSION] Original size: {len(file_content)} bytes, PDF size: {len(pdf_content)} bytes")
            logger.info("=" * 80)

            return {
                "converted": True,
                "pdf_content": pdf_content,
                "pdf_filename": pdf_filename,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"[PDF CONVERSION] ❌ PDF conversion error for {filename}")
            logger.error(f"[PDF CONVERSION] Error type: {type(e).__name__}")
            logger.error(f"[PDF CONVERSION] Error message: {e}")
            import traceback
            logger.error(f"[PDF CONVERSION] Traceback:\n{traceback.format_exc()}")
            logger.info("=" * 80)
            return {
                "converted": False,
                "status": "failed",
                "error": str(e),
            }
