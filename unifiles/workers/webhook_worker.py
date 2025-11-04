"""
Webhook Worker - 处理 Webhook 事件分发任务

功能：
- 接收 Webhook 分发任务
- 读取用户配置的 Webhook 端点
- 发送 HTTP POST 请求到目标端点
- 处理重试逻辑（指数退避）
- 记录分发结果和错误
- 支持签名验证（HMAC-SHA256）

使用场景：
- 文件上传完成通知
- 文件处理完成通知
- 任务状态变更通知
- 系统事件通知
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from unifiles.core.queue import EventChannels, QueueNames, TaskTypes
from unifiles.core.services.queue_service import QueueService
from unifiles.workers.base_worker import BaseWorker


class WebhookWorker(BaseWorker):
    """
    Webhook 分发 Worker

    从 unifiles:queue:webhook_dispatch 队列中取出任务，发送 HTTP 请求到用户配置的端点

    任务数据格式：
    {
        "task_id": "task_xxx",
        "user_id": "user_xxx",
        "task_data": {
            "event_type": "file.uploaded",        # 事件类型
            "webhook_urls": [                     # Webhook 端点列表
                "https://example.com/webhook1",
                "https://example.com/webhook2"
            ],
            "payload": {                          # 事件数据
                "file_id": "file_xxx",
                "filename": "document.pdf",
                "size": 1024000,
                "timestamp": "2024-01-01T12:00:00Z"
            },
            "signature_secret": "secret_key"      # 签名密钥（可选）
        }
    }

    使用示例：
    ```python
    worker = WebhookWorker(concurrency=8)
    await worker.start()
    ```
    """

    def __init__(
        self,
        concurrency: int = 8,
        request_timeout: int = 30,
        max_retries_per_url: int = 3,
    ):
        """
        初始化 Webhook Worker

        Args:
            concurrency: 并发分发数（默认 8）
            request_timeout: HTTP 请求超时时间（秒）
            max_retries_per_url: 每个 URL 的最大重试次数
        """
        super().__init__(
            queue_name=QueueNames.WEBHOOK_DISPATCH,
            worker_name="WebhookWorker",
            concurrency=concurrency,
            use_priority_queue=False,
        )

        self.request_timeout = request_timeout
        self.max_retries_per_url = max_retries_per_url

        # HTTP 客户端（复用连接）
        self._http_client: Optional[httpx.AsyncClient] = None

        # 统计信息扩展
        self.webhook_stats = {
            "total_requests_sent": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "total_retry_attempts": 0,
            "avg_response_time": 0.0,
        }

    async def start(self):
        """启动 Worker（初始化 HTTP 客户端）"""
        logger.info(
            f"Initializing {self.worker_name} with timeout={self.request_timeout}s"
        )

        # 创建 HTTP 客户端（支持 HTTP/2）
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.request_timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            http2=True,
        )

        # 调用父类启动
        await super().start()

    async def _cleanup(self):
        """清理资源"""
        if self._http_client:
            await self._http_client.aclose()
            logger.info("HTTP client closed")

        await super()._cleanup()

    # ===== 核心任务处理 =====

    async def process_task(self, task: dict):
        """
        处理 Webhook 分发任务

        Args:
            task: 任务数据

        Raises:
            Exception: 分发失败时抛出（会触发重试）
        """
        import time

        start_time = time.time()

        task_id = task.get("task_id")
        user_id = task.get("user_id")
        task_data = task.get("task_data", {})

        event_type = task_data.get("event_type", "unknown")
        webhook_urls = task_data.get("webhook_urls", [])
        payload = task_data.get("payload", {})
        signature_secret = task_data.get("signature_secret")

        logger.info(
            f"Processing webhook task {task_id}: event={event_type}, "
            f"urls={len(webhook_urls)}"
        )

        if not webhook_urls:
            logger.warning(f"No webhook URLs configured for task {task_id}")
            return

        # 构建 Webhook 请求体
        webhook_payload = self._build_webhook_payload(event_type, payload)

        # 生成签名
        signature = None
        if signature_secret:
            signature = self._generate_signature(webhook_payload, signature_secret)

        # 分发到所有配置的 URL（并行）
        results = await self._dispatch_to_urls(
            task_id=task_id,
            webhook_urls=webhook_urls,
            payload=webhook_payload,
            signature=signature,
        )

        # 统计结果
        successful_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - successful_count

        self.webhook_stats["successful_deliveries"] += successful_count
        self.webhook_stats["failed_deliveries"] += failed_count

        # 记录到数据库
        await self._log_webhook_results(
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            results=results,
        )

        # 如果全部失败，抛出异常触发任务重试
        if failed_count == len(results):
            raise Exception(
                f"All webhook deliveries failed ({failed_count}/{len(results)})"
            )

        # 部分失败，记录警告
        if failed_count > 0:
            logger.warning(
                f"Webhook task {task_id} completed with {failed_count}/{len(results)} failures"
            )

        logger.success(
            f"Webhook task {task_id} completed: {successful_count}/{len(results)} successful "
            f"({time.time() - start_time:.2f}s)"
        )

    # ===== 辅助方法 =====

    def _build_webhook_payload(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建 Webhook 请求体

        Args:
            event_type: 事件类型
            event_data: 事件数据

        Returns:
            Webhook 请求体
        """
        return {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": event_data,
        }

    def _generate_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """
        生成 Webhook 签名（HMAC-SHA256）

        Args:
            payload: 请求体
            secret: 签名密钥

        Returns:
            签名字符串
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"

    async def _dispatch_to_urls(
        self,
        task_id: str,
        webhook_urls: List[str],
        payload: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        并行分发到所有 URL

        Args:
            task_id: 任务 ID
            webhook_urls: Webhook URL 列表
            payload: 请求体
            signature: 签名（可选）

        Returns:
            每个 URL 的分发结果列表
        """
        # 创建并发任务
        tasks = [
            self._send_webhook_request(url, payload, signature)
            for url in webhook_urls
        ]

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        formatted_results = []
        for url, result in zip(webhook_urls, results):
            if isinstance(result, Exception):
                formatted_results.append(
                    {
                        "url": url,
                        "success": False,
                        "error": str(result),
                        "status_code": None,
                        "response_time": None,
                    }
                )
            else:
                formatted_results.append(result)

        return formatted_results

    async def _send_webhook_request(
        self, url: str, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送单个 Webhook 请求（带重试）

        Args:
            url: Webhook URL
            payload: 请求体
            signature: 签名（可选）

        Returns:
            分发结果
        """
        import time

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Unifiles-Webhook/1.0",
        }

        if signature:
            headers["X-Webhook-Signature"] = signature

        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries_per_url:
            try:
                start_time = time.time()

                response = await self._http_client.post(
                    url, json=payload, headers=headers
                )

                response_time = time.time() - start_time

                self.webhook_stats["total_requests_sent"] += 1

                # 检查响应状态
                if response.status_code >= 200 and response.status_code < 300:
                    logger.success(
                        f"Webhook delivered to {url}: {response.status_code} "
                        f"({response_time:.2f}s)"
                    )

                    return {
                        "url": url,
                        "success": True,
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "retry_count": retry_count,
                    }
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    logger.warning(
                        f"Webhook delivery failed to {url}: {last_error} "
                        f"(attempt {retry_count + 1}/{self.max_retries_per_url + 1})"
                    )

            except httpx.TimeoutException as e:
                last_error = f"Timeout after {self.request_timeout}s"
                logger.warning(f"Webhook timeout for {url}: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Webhook delivery error to {url}: {last_error} "
                    f"(attempt {retry_count + 1}/{self.max_retries_per_url + 1})"
                )

            # 重试（指数退避）
            if retry_count < self.max_retries_per_url:
                retry_delay = 2**retry_count  # 1s, 2s, 4s
                await asyncio.sleep(retry_delay)
                retry_count += 1
                self.webhook_stats["total_retry_attempts"] += 1
            else:
                break

        # 所有重试都失败
        logger.error(
            f"Webhook delivery permanently failed to {url} after "
            f"{self.max_retries_per_url + 1} attempts: {last_error}"
        )

        return {
            "url": url,
            "success": False,
            "error": last_error,
            "status_code": None,
            "response_time": None,
            "retry_count": retry_count,
        }

    async def _log_webhook_results(
        self,
        task_id: str,
        user_id: str,
        event_type: str,
        results: List[Dict[str, Any]],
    ):
        """
        记录 Webhook 分发结果到数据库

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            event_type: 事件类型
            results: 分发结果列表
        """
        try:
            # TODO: 将结果记录到 webhook_logs 表
            # 这里暂时记录到日志

            summary = {
                "task_id": task_id,
                "user_id": user_id,
                "event_type": event_type,
                "total_urls": len(results),
                "successful": sum(1 for r in results if r["success"]),
                "failed": sum(1 for r in results if not r["success"]),
                "details": results,
            }

            logger.info(f"Webhook results: {json.dumps(summary, indent=2)}")

        except Exception as e:
            logger.error(f"Failed to log webhook results: {e}")

    # ===== 监控和统计 =====

    def get_stats(self) -> Dict[str, Any]:
        """获取 Worker 统计信息（扩展）"""
        base_stats = super().get_stats()

        return {
            **base_stats,
            "total_requests_sent": self.webhook_stats["total_requests_sent"],
            "successful_deliveries": self.webhook_stats["successful_deliveries"],
            "failed_deliveries": self.webhook_stats["failed_deliveries"],
            "total_retry_attempts": self.webhook_stats["total_retry_attempts"],
            "success_rate_percent": (
                round(
                    self.webhook_stats["successful_deliveries"]
                    / self.webhook_stats["total_requests_sent"]
                    * 100,
                    2,
                )
                if self.webhook_stats["total_requests_sent"] > 0
                else 0.0
            ),
        }


# ===== 启动脚本 =====

if __name__ == "__main__":
    """
    独立运行 WebhookWorker

    用法：
    python -m unifiles.workers.webhook_worker
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
        worker = WebhookWorker(concurrency=8)

        try:
            await worker.start()
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
            await worker.stop()

    asyncio.run(main())
