"""
文件处理 Worker - 处理 OCR、AI 分析等耗时任务

功能：
- 接收文件处理任务（OCR、文本提取、AI 分析等）
- 使用信号量控制并发资源（避免 OCR 进程过多）
- 从存储后端下载文件
- 调用处理服务（OCR、AI 等）
- 更新处理结果到数据库
- 发布处理完成事件

资源控制：
- 使用 Redis 信号量限制并发 OCR 进程（默认最多 4 个）
- 付费用户可以使用优先级队列获得优先处理
"""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from unifiles.core.queue import EventChannels, QueueNames, TaskTypes
from unifiles.core.services.file_service import FileService
from unifiles.core.services.storage_service import StorageService
from unifiles.workers.base_worker import BaseWorker


class FileProcessWorker(BaseWorker):
    """
    文件处理 Worker

    从 unifiles:queue:file_process 或 unifiles:queue:file_process:priority 队列取出任务

    任务数据格式：
    {
        "task_id": "task_xxx",
        "user_id": "user_xxx",
        "file_id": "file_xxx",
        "task_data": {
            "format": "pdf",
            "processing_type": "ocr",           # ocr, text_extract, ai_analysis
            "options": {
                "language": "eng+chi_sim",      # OCR 语言
                "extract_tables": true,         # 是否提取表格
                "enable_ai": true               # 是否启用 AI 分析
            }
        }
    }

    使用示例：
    ```python
    # 普通队列 Worker
    worker = FileProcessWorker(concurrency=2, use_priority_queue=False)
    await worker.start()

    # 优先级队列 Worker（付费用户）
    priority_worker = FileProcessWorker(concurrency=2, use_priority_queue=True)
    await priority_worker.start()
    ```
    """

    def __init__(
        self,
        concurrency: int = 2,
        use_priority_queue: bool = False,
        max_ocr_concurrent: int = 4,
    ):
        """
        初始化文件处理 Worker

        Args:
            concurrency: 并发处理数（默认 2，因为 OCR 很耗资源）
            use_priority_queue: 是否使用优先级队列
            max_ocr_concurrent: 最大并发 OCR 进程数（使用信号量控制）
        """
        queue_name = (
            QueueNames.FILE_PROCESS_PRIORITY
            if use_priority_queue
            else QueueNames.FILE_PROCESS
        )

        super().__init__(
            queue_name=queue_name,
            worker_name=f"FileProcessWorker{'[Priority]' if use_priority_queue else ''}",
            concurrency=concurrency,
            use_priority_queue=use_priority_queue,
        )

        self.max_ocr_concurrent = max_ocr_concurrent
        self.file_service = FileService()
        self.storage_service = StorageService()

        # OCR 信号量资源名（全局共享）
        self.ocr_semaphore_resource = "unifiles:semaphore:ocr"

        # 统计信息扩展
        self.process_stats = {
            "total_pages_processed": 0,
            "total_text_extracted": 0,
            "ocr_timeouts": 0,
            "processing_time_total": 0,
        }

    async def start(self):
        """启动 Worker（初始化服务）"""
        logger.info(
            f"Initializing {self.worker_name} with max_ocr_concurrent={self.max_ocr_concurrent}"
        )

        # 初始化服务
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
        处理文件处理任务

        Args:
            task: 任务数据

        Raises:
            Exception: 处理失败时抛出
        """
        import time

        start_time = time.time()

        task_id = task.get("task_id")
        user_id = task.get("user_id")
        file_id = task.get("file_id")
        task_data = task.get("task_data", {})

        file_format = task_data.get("format", "unknown")
        processing_type = task_data.get("processing_type", "ocr")
        options = task_data.get("options", {})

        logger.info(
            f"Processing task {task_id}: file={file_id}, "
            f"format={file_format}, type={processing_type}"
        )

        # 1. 获取信号量（控制并发 OCR 进程）
        semaphore_acquired = False
        if processing_type == "ocr":
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=5, message="Waiting for OCR resource..."
            )

            semaphore_acquired = await self.queue_service.queue_client.semaphore_acquire(
                resource=self.ocr_semaphore_resource,
                max_count=self.max_ocr_concurrent,
                timeout=300,  # 最多等待 5 分钟
            )

            if not semaphore_acquired:
                raise Exception("Failed to acquire OCR semaphore (timeout)")

            logger.info(f"OCR semaphore acquired for task {task_id}")

        try:
            # 2. 验证文件记录
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=10, message="Verifying file..."
            )

            file_record = await self._verify_file_access(file_id, user_id)

            # 3. 从存储下载文件数据
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=20, message="Downloading file..."
            )

            file_data = await self._download_file(file_record)

            # 4. 执行处理
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=30, message=f"Processing ({processing_type})..."
            )

            result = await self._execute_processing(
                task_id=task_id,
                file_id=file_id,
                file_data=file_data,
                file_format=file_format,
                processing_type=processing_type,
                options=options,
            )

            # 5. 保存处理结果
            await self.queue_service.task_service.update_progress(
                task_id=task_id, progress=90, message="Saving results..."
            )

            await self._save_processing_result(file_id, processing_type, result)

            # 6. 发布处理完成事件
            await self.queue_service.publish_event(
                channel=EventChannels.FILE_PROCESS,
                event_data={
                    "event": "file_processed",
                    "file_id": file_id,
                    "user_id": user_id,
                    "processing_type": processing_type,
                    "result_summary": {
                        "pages": result.get("pages", 0),
                        "text_length": len(result.get("text", "")),
                    },
                },
            )

            # 更新统计
            self.process_stats["total_pages_processed"] += result.get("pages", 1)
            self.process_stats["total_text_extracted"] += len(result.get("text", ""))
            self.process_stats["processing_time_total"] += time.time() - start_time

            logger.success(
                f"File {file_id} processed successfully: {processing_type} "
                f"({time.time() - start_time:.2f}s)"
            )

        finally:
            # 7. 释放信号量
            if semaphore_acquired:
                await self.queue_service.queue_client.semaphore_release(
                    self.ocr_semaphore_resource
                )
                logger.info(f"OCR semaphore released for task {task_id}")

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
            file_record = await self.file_service.get_file(file_id, user_id)

            if not file_record:
                raise Exception(f"File {file_id} not found or access denied")

            # 检查文件状态
            if file_record.get("status") != "uploaded":
                raise Exception(
                    f"File {file_id} is not in uploaded state: {file_record.get('status')}"
                )

            return file_record

        except Exception as e:
            logger.error(f"Failed to verify file access: {e}")
            raise

    async def _download_file(self, file_record: Dict[str, Any]) -> bytes:
        """
        从存储后端下载文件

        Args:
            file_record: 文件记录

        Returns:
            文件数据

        Raises:
            Exception: 下载失败
        """
        try:
            storage_backend = file_record.get("storage_backend", "minio")
            storage_path = file_record.get("storage_path")

            if not storage_path:
                raise Exception("Storage path not found in file record")

            # 使用 StorageService 下载
            file_data = await self.storage_service.download(
                backend=storage_backend, key=storage_path
            )

            logger.info(
                f"File downloaded from {storage_backend}: {storage_path} "
                f"({len(file_data)} bytes)"
            )

            return file_data

        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise

    async def _execute_processing(
        self,
        task_id: str,
        file_id: str,
        file_data: bytes,
        file_format: str,
        processing_type: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行文件处理（OCR、文本提取等）

        Args:
            task_id: 任务 ID
            file_id: 文件 ID
            file_data: 文件数据
            file_format: 文件格式
            processing_type: 处理类型
            options: 处理选项

        Returns:
            处理结果字典

        Raises:
            Exception: 处理失败
        """
        try:
            if processing_type == "ocr":
                return await self._execute_ocr(
                    task_id, file_id, file_data, file_format, options
                )
            elif processing_type == "text_extract":
                return await self._execute_text_extract(file_data, file_format)
            elif processing_type == "ai_analysis":
                return await self._execute_ai_analysis(file_data, file_format, options)
            else:
                raise Exception(f"Unknown processing type: {processing_type}")

        except Exception as e:
            logger.error(f"Error executing processing: {e}")
            raise

    async def _execute_ocr(
        self,
        task_id: str,
        file_id: str,
        file_data: bytes,
        file_format: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行 OCR 处理

        Args:
            task_id: 任务 ID
            file_id: 文件 ID
            file_data: 文件数据
            file_format: 文件格式
            options: OCR 选项

        Returns:
            OCR 结果
        """
        logger.info(f"Starting OCR for file {file_id} (format: {file_format})")

        # TODO: 实际的 OCR 调用（集成 Tesseract、PaddleOCR 等）
        # 这里使用模拟实现

        await asyncio.sleep(2)  # 模拟 OCR 耗时

        # 模拟结果
        result = {
            "text": f"[OCR Result for {file_id}]\nThis is extracted text from the document...",
            "pages": 3,
            "confidence": 0.95,
            "language": options.get("language", "eng"),
        }

        # 更新进度
        await self.queue_service.task_service.update_progress(
            task_id=task_id, progress=70, message="OCR completed, post-processing..."
        )

        return result

    async def _execute_text_extract(
        self, file_data: bytes, file_format: str
    ) -> Dict[str, Any]:
        """
        执行文本提取（纯文本、PDF 等）

        Args:
            file_data: 文件数据
            file_format: 文件格式

        Returns:
            提取结果
        """
        logger.info(f"Extracting text from format: {file_format}")

        # TODO: 实际的文本提取（PyPDF2、python-docx 等）
        await asyncio.sleep(1)

        result = {
            "text": f"[Extracted Text]\nContent from {file_format} file...",
            "pages": 1,
        }

        return result

    async def _execute_ai_analysis(
        self, file_data: bytes, file_format: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 AI 分析（分类、摘要等）

        Args:
            file_data: 文件数据
            file_format: 文件格式
            options: AI 选项

        Returns:
            分析结果
        """
        logger.info(f"Running AI analysis on format: {file_format}")

        # TODO: 实际的 AI 调用（OpenAI、本地模型等）
        await asyncio.sleep(3)

        result = {
            "analysis": {
                "category": "document",
                "summary": "This is a document about...",
                "keywords": ["keyword1", "keyword2"],
            },
            "confidence": 0.89,
        }

        return result

    async def _save_processing_result(
        self, file_id: str, processing_type: str, result: Dict[str, Any]
    ):
        """
        保存处理结果到数据库

        Args:
            file_id: 文件 ID
            processing_type: 处理类型
            result: 处理结果
        """
        try:
            import json

            # 更新文件记录（添加处理结果到元数据）
            async with self.file_service._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE unifiles.files
                    SET
                        metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb,
                        status = 'processed',
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    json.dumps({f"{processing_type}_result": result}),
                    file_id,
                )

            logger.info(f"Processing result saved for file {file_id}")

        except Exception as e:
            logger.error(f"Failed to save processing result: {e}")
            # 不抛出异常，因为处理已完成

    # ===== 监控和统计 =====

    def get_stats(self) -> Dict[str, Any]:
        """获取 Worker 统计信息（扩展）"""
        base_stats = super().get_stats()

        return {
            **base_stats,
            "total_pages_processed": self.process_stats["total_pages_processed"],
            "total_text_extracted": self.process_stats["total_text_extracted"],
            "ocr_timeouts": self.process_stats["ocr_timeouts"],
            "avg_processing_time": (
                round(
                    self.process_stats["processing_time_total"]
                    / base_stats["tasks_processed"],
                    2,
                )
                if base_stats["tasks_processed"] > 0
                else 0
            ),
        }


# ===== 启动脚本 =====

if __name__ == "__main__":
    """
    独立运行 FileProcessWorker

    用法：
    python -m unifiles.workers.process_worker [--priority]
    """
    import sys

    async def main():
        # 解析参数
        use_priority = "--priority" in sys.argv

        # 配置日志
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        )

        # 创建并启动 Worker
        worker = FileProcessWorker(concurrency=2, use_priority_queue=use_priority)

        try:
            await worker.start()
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
            await worker.stop()

    asyncio.run(main())
