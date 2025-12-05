"""
Celery 应用实例
初始化 Celery 应用并配置 RabbitMQ 连接
"""

from celery import Celery

from unifiles.core.celery.config import CeleryConfig
from unifiles.core.logging import get_logger

logger = get_logger()

# 创建配置实例
celery_config = CeleryConfig()

# 初始化 Celery 应用
# main 参数指定应用名称，用于识别任务
celery_app = Celery("unifiles")

# 应用配置
config_dict = celery_config.get_config()
celery_app.conf.update(config_dict)

logger.info("Celery application initialized")
logger.info(f"Broker URL: {celery_config.broker_url}")
logger.info(f"Result Backend: {celery_config.result_backend}")
logger.info(f"Worker Concurrency: {celery_config.worker_concurrency}")


# 自动发现任务
# 这会自动导入 unifiles.core.celery.tasks 中定义的所有任务
celery_app.autodiscover_tasks(["unifiles.core.celery"])


@celery_app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试 Celery 是否正常工作"""
    logger.info(f"Request: {self.request!r}")
    return {"status": "ok", "message": "Celery is working!"}
