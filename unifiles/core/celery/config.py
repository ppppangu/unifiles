"""
Celery 配置模块
从环境变量读取 RabbitMQ 和 Celery 相关配置
"""
from typing import Any, Dict

from unifiles.core.config.env_config import EnvironmentConfig


class CeleryConfig:
    """Celery 配置类"""

    def __init__(self, env_config: EnvironmentConfig | None = None):
        """
        初始化 Celery 配置

        Args:
            env_config: 环境配置实例，如果为 None 则创建新实例
        """
        self.env_config = env_config or EnvironmentConfig()

    def get_config(self) -> Dict[str, Any]:
        """
        获取 Celery 配置字典

        Returns:
            Celery 配置字典
        """
        return {
            # Broker 配置（RabbitMQ）
            "broker_url": self.env_config.get_env_value(
                "UNIFILES_CELERY_BROKER_URL",
                default="amqp://guest:guest@localhost:5672//",
            ),
            # 结果后端（RabbitMQ RPC）
            "result_backend": self.env_config.get_env_value(
                "UNIFILES_CELERY_RESULT_BACKEND",
                default="rpc://",
            ),
            # 任务追踪
            "task_track_started": self.env_config.get_env_value(
                "UNIFILES_CELERY_TASK_TRACK_STARTED",
                default="true",
                cast_type=bool,
            ),
            # 任务超时（秒）
            "task_time_limit": self.env_config.get_env_value(
                "UNIFILES_CELERY_TASK_TIME_LIMIT",
                default="600",
                cast_type=int,
            ),
            # 任务软超时（秒），在硬超时前发送 SoftTimeLimitExceeded 异常
            "task_soft_time_limit": self.env_config.get_env_value(
                "UNIFILES_CELERY_TASK_TIME_LIMIT",
                default="600",
                cast_type=int,
            )
            - 30,  # 提前 30 秒
            # Worker 并发数
            "worker_concurrency": self.env_config.get_env_value(
                "UNIFILES_CELERY_WORKER_CONCURRENCY",
                default="4",
                cast_type=int,
            ),
            # 任务序列化格式
            "task_serializer": self.env_config.get_env_value(
                "UNIFILES_CELERY_TASK_SERIALIZER",
                default="json",
            ),
            # 结果序列化格式
            "result_serializer": self.env_config.get_env_value(
                "UNIFILES_CELERY_RESULT_SERIALIZER",
                default="json",
            ),
            # 接受的序列化格式
            "accept_content": ["json"],
            # 时区
            "timezone": "Asia/Shanghai",
            # 结果过期时间（秒）
            "result_expires": self.env_config.get_env_value(
                "UNIFILES_CELERY_RESULT_EXPIRES",
                default="3600",
                cast_type=int,
            ),
            # 任务队列配置
            "task_default_queue": self.env_config.get_env_value(
                "UNIFILES_CELERY_DEFAULT_QUEUE",
                default="unifiles_default",
            ),
            # 任务路由
            "task_routes": {
                "unifiles.core.celery.tasks.process_file_extraction_task": {
                    "queue": self.env_config.get_env_value(
                        "UNIFILES_CELERY_EXTRACTION_QUEUE",
                        default="unifiles_extraction",
                    )
                }
            },
            # Worker 配置
            "worker_prefetch_multiplier": 1,  # 每次只获取一个任务，避免长任务阻塞
            "worker_max_tasks_per_child": 100,  # Worker 处理 100 个任务后重启，防止内存泄漏
            # 任务结果配置
            "result_extended": True,  # 返回更详细的结果信息
            # 任务 acks late（任务完成后才确认，避免任务丢失）
            "task_acks_late": True,
            # 任务拒绝时重新入队
            "task_reject_on_worker_lost": True,
        }

    @property
    def broker_url(self) -> str:
        """获取 Broker URL"""
        return self.env_config.get_env_value(
            "UNIFILES_CELERY_BROKER_URL",
            default="amqp://guest:guest@localhost:5672//",
        )

    @property
    def result_backend(self) -> str:
        """获取结果后端 URL"""
        return self.env_config.get_env_value(
            "UNIFILES_CELERY_RESULT_BACKEND",
            default="rpc://",
        )

    @property
    def worker_concurrency(self) -> int:
        """获取 Worker 并发数"""
        return self.env_config.get_env_value(
            "UNIFILES_CELERY_WORKER_CONCURRENCY",
            default="4",
            cast_type=int,
        )
