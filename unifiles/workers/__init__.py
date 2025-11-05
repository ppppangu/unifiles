"""
Unifiles Workers - 异步任务处理器

提供：
- BaseWorker: Worker 基类
- FileUploadWorker: 文件上传 Worker
- FileProcessWorker: 文件处理 Worker（OCR、AI 分析等）
- WebhookWorker: Webhook 分发 Worker

使用示例：
```python
from unifiles.workers import FileUploadWorker, FileProcessWorker, WebhookWorker

# 启动所有 Workers
async def start_all_workers():
    upload_worker = FileUploadWorker(concurrency=4)
    process_worker = FileProcessWorker(concurrency=2)
    webhook_worker = WebhookWorker(concurrency=8)

    await asyncio.gather(
        upload_worker.start(),
        process_worker.start(),
        webhook_worker.start()
    )
```
"""

from unifiles.workers.base_worker import BaseWorker
from unifiles.workers.upload_worker import FileUploadWorker
from unifiles.workers.process_worker import FileProcessWorker
from unifiles.workers.webhook_worker import WebhookWorker

__all__ = [
    "BaseWorker",
    "FileUploadWorker",
    "FileProcessWorker",
    "WebhookWorker",
]
