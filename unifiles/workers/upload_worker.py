"""
文件上传 Worker - 处理异步文件上传任务

功能：
- 接收文件上传任务（文件 ID + 存储后端信息）
- 将文件从临时位置上传到最终存储位置（MinIO/S3/本地）
- 更新文件状态和元数据
- 触发后续处理流程（如需要）

处理流程：
1. 从队列取出上传任务
2. 验证文件和用户权限
3. 读取临时文件数据
4. 上传到目标存储后端
5. 更新数据库中的文件状态
6. 清理临时文件
7. 发布上传完成事件（可选触发处理任务）
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from unifiles.core.queue import EventChannels, QueueNames, TaskTypes
from unifiles.core.services.file_service import FileService
from unifiles.core.services.storage_service import StorageService
from unifiles.workers.base_worker import BaseWorker


class FileUploadWorker(BaseWorker):
    """
    文件上传 Worker

    从 unifiles:queue:file_upload 队列中取出任务，异步上传文件到存储后端

    任务数据格式：
    {
        "task_id": "task_xxx",
        "user_id": "user_xxx",
        "file_id": "file_xxx",
        "task_data": {
            "temp_file_path": "/tmp/upload_xxx",  # 临时文件路径
            "storage_backend": "minio",            # 存储后端
            "content_type": "application/pdf",
            "original_filename": "document.pdf",
            "file_size": 1024000,
            "trigger_processing": true             # 是否自动触发处理
        }
    }

    使用示例：
    ```python
    worker = FileUploadWorker(concurrency=4)
    await worker.start()
    ```
    """

    def __init__(
        self,
        concurrency: int = 4,
        temp_dir: Optional[str] = None,
    ):
        """
        初始化文件上传 Worker

        Args:
            concurrency: 并发上传数（默认 4）
            temp_dir: 临时文件目录（可选）
        """
        super().__init__(
            queue_name=QueueNames.FILE_UPLOAD,
            worker_name="FileUploadWorker",
            concurrency=concurrency,
            use_priority_queue=False,
        )

        self.temp_dir = temp_dir or "/tmp/unifiles_uploads"
        self.file_service = FileService()
        self.storage_service = StorageService()

        # 统计信息扩展
        self.upload_stats = {
            "total_bytes_uploaded": 0,
            "failed_uploads": 0,
            "temp_files_cleaned": 0,
        }

    async def start(self):
        """启动 Worker（初始化存储服务）"""
        logger.info(f"Initializing {self.worker_name} with temp_dir={self.temp_dir}")

        # 确保临时目录存在
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

        # 初始化存储和文件服务
        await self.storage_service.init()
        await self.file_service.init_pool()

        # 调用父类启动
        await super().start()

    async def _cleanup(self):
        """清理资源"""
        await self.file_service.close_pool()
        await self.storage_service.close()
        await super()._cleanup()

    # ===== 核心任务处理 =====

    async def process_task(self, task: dict):
        """
        处理文件上传任务

        Args:
            task: 任务数据

        Raises:
            Exception: 上传失败时抛出
        """
        task_id = task.get("task_id")
        user_id = task.get("user_id")
        file_id = task.get("file_id")
        task_data = task.get("task_data", {})

        temp_file_path = task_data.get("temp_file_path")
        storage_backend = task_data.get("storage_backend", "minio")
        content_type = task_data.get("content_type", "application/octet-stream")
        original_filename = task_data.get("original_filename", "unknown")
        file_size = task_data.get("file_size", 0)
        trigger_processing = task_data.get("trigger_processing", False)

        logger.info(
            f"Processing upload task {task_id}: file={file_id}, "
            f"size={file_size}, backend={storage_backend}"
        )

        # 1. 验证临时文件存在
        if not temp_file_path or not os.path.exists(temp_file_path):
            raise FileNotFoundError(
                f"Temporary file not found: {temp_file_path}"
            )

        try:
            # 2. 更新进度：准备上传
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=10, message="Preparing upload..."
            )

            # 3. 验证文件记录和权限
            file_record = await self._verify_file_access(file_id, user_id)

            # 4. 读取文件数据
            with open(temp_file_path, "rb") as f:
                file_data = f.read()

            actual_size = len(file_data)
            if actual_size != file_size:
                logger.warning(
                    f"File size mismatch: expected {file_size}, got {actual_size}"
                )

            # 5. 上传到存储后端
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=30, message="Uploading to storage..."
            )

            storage_path = await self._upload_to_storage(
                file_id=file_id,
                file_data=file_data,
                content_type=content_type,
                storage_backend=storage_backend,
            )

            # 6. 更新数据库中的文件记录
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=80, message="Updating file metadata..."
            )

            await self._update_file_record(
                file_id=file_id,
                storage_path=storage_path,
                storage_backend=storage_backend,
                file_size=actual_size,
            )

            # 7. 清理临时文件
            await self._cleanup_temp_file(temp_file_path)

            # 8. 发布上传完成事件
            await self.queue_service.publish_event(
                channel=EventChannels.FILE_UPLOADS,
                event_data={
                    "event": "file_uploaded",
                    "file_id": file_id,
                    "user_id": user_id,
                    "storage_backend": storage_backend,
                    "file_size": actual_size,
                },
            )

            # 9. 如果需要，触发处理任务
            if trigger_processing:
                await self._trigger_processing(file_id, user_id, file_record)

            # 更新统计
            self.upload_stats["total_bytes_uploaded"] += actual_size

            logger.success(
                f"File {file_id} uploaded successfully: {actual_size} bytes to {storage_backend}"
            )

        except Exception as e:
            self.upload_stats["failed_uploads"] += 1
            logger.error(f"Error uploading file {file_id}: {e}")
            raise

    # ===== 辅助方法 =====

    async def _verify_file_access(
        self, file_id: str, user_id: str
    ) -> Dict[str, Any]:
        """
        验证文件记录和用户权限

        Args:
            file_id: 文件 ID
            user_id: 用户 ID

        Returns:
            文件记录

        Raises:
            Exception: 文件不存在或无权访问
        """
        try:
            # 通过 FileService 获取文件信息（自动验证权限）
            file_record = await self.file_service.get_file(file_id, user_id)

            if not file_record:
                raise Exception(f"File {file_id} not found or access denied")

            return file_record

        except Exception as e:
            logger.error(f"Failed to verify file access: {e}")
            raise

    async def _upload_to_storage(
        self,
        file_id: str,
        file_data: bytes,
        content_type: str,
        storage_backend: str,
    ) -> str:
        """
        上传文件到存储后端

        Args:
            file_id: 文件 ID
            file_data: 文件数据
            content_type: 内容类型
            storage_backend: 存储后端

        Returns:
            存储路径

        Raises:
            Exception: 上传失败
        """
        try:
            # 生成存储路径（使用文件 ID 作为对象键）
            storage_path = f"files/{file_id}"

            # 使用 StorageService 上传
            await self.storage_service.upload(
                backend=storage_backend,
                key=storage_path,
                data=file_data,
                content_type=content_type,
            )

            logger.info(
                f"File uploaded to {storage_backend}: {storage_path} "
                f"({len(file_data)} bytes)"
            )

            return storage_path

        except Exception as e:
            logger.error(f"Failed to upload to storage: {e}")
            raise

    async def _update_file_record(
        self,
        file_id: str,
        storage_path: str,
        storage_backend: str,
        file_size: int,
    ):
        """
        更新数据库中的文件记录

        Args:
            file_id: 文件 ID
            storage_path: 存储路径
            storage_backend: 存储后端
            file_size: 文件大小
        """
        try:
            # 调用数据库更新函数
            async with self.file_service._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE unifiles.files
                    SET
                        storage_path = $1,
                        storage_backend = $2,
                        size_bytes = $3,
                        status = 'uploaded',
                        updated_at = NOW()
                    WHERE id = $4
                    """,
                    storage_path,
                    storage_backend,
                    file_size,
                    file_id,
                )

            logger.info(f"File record updated: {file_id}")

        except Exception as e:
            logger.error(f"Failed to update file record: {e}")
            # 不抛出异常，因为文件已上传成功

    async def _cleanup_temp_file(self, temp_file_path: str):
        """
        清理临时文件

        Args:
            temp_file_path: 临时文件路径
        """
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                self.upload_stats["temp_files_cleaned"] += 1
                logger.debug(f"Temporary file cleaned: {temp_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean temporary file {temp_file_path}: {e}")

    async def _trigger_processing(
        self, file_id: str, user_id: str, file_record: Dict[str, Any]
    ):
        """
        触发文件处理任务（如果需要）

        Args:
            file_id: 文件 ID
            user_id: 用户 ID
            file_record: 文件记录
        """
        try:
            # 获取文件格式
            file_format = file_record.get("format", "").lower()

            # 判断是否需要处理（支持 OCR 的格式）
            processable_formats = ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"]

            if file_format not in processable_formats:
                logger.info(
                    f"File {file_id} format '{file_format}' does not require processing"
                )
                return

            # 创建处理任务
            logger.info(f"Triggering processing task for file {file_id}")

            processing_task = await self.queue_service.enqueue_task(
                user_id=user_id,
                queue_name=QueueNames.FILE_PROCESS,
                task_type=TaskTypes.FILE_PROCESS,
                task_data={
                    "file_id": file_id,
                    "format": file_format,
                    "processing_type": "ocr",
                },
                file_id=file_id,
                priority=10,  # 普通优先级
            )

            logger.success(
                f"Processing task created: {processing_task['task_id']} for file {file_id}"
            )

        except Exception as e:
            logger.error(f"Failed to trigger processing for {file_id}: {e}")
            # 不抛出异常，因为上传已成功

    # ===== 监控和统计 =====

    def get_stats(self) -> Dict[str, Any]:
        """获取 Worker 统计信息（扩展）"""
        base_stats = super().get_stats()

        return {
            **base_stats,
            "total_bytes_uploaded": self.upload_stats["total_bytes_uploaded"],
            "failed_uploads": self.upload_stats["failed_uploads"],
            "temp_files_cleaned": self.upload_stats["temp_files_cleaned"],
            "avg_bytes_per_task": (
                round(
                    self.upload_stats["total_bytes_uploaded"]
                    / base_stats["tasks_processed"]
                )
                if base_stats["tasks_processed"] > 0
                else 0
            ),
        }


# ===== 启动脚本 =====

if __name__ == "__main__":
    """
    独立运行 FileUploadWorker

    用法：
    python -m unifiles.workers.upload_worker
    """
    import sys

    async def main():
        # 配置日志
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        )

        # 创建并启动 Worker
        worker = FileUploadWorker(concurrency=4)

        try:
            await worker.start()
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
            await worker.stop()

    asyncio.run(main())
