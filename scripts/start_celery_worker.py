#!/usr/bin/env python
"""
Celery Worker 启动脚本

使用示例:
    python scripts/start_celery_worker.py --concurrency 4 --loglevel INFO
    python scripts/start_celery_worker.py --queues unifiles_extraction --concurrency 2
    Windows环境下只支持solo: uv run python scripts/start_celery_worker.py --pool solo --loglevel INFO
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unifiles.core.celery.app import celery_app
from unifiles.core.celery.config import CeleryConfig
from unifiles.core.logging import get_logger

logger = get_logger()


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Start Celery Worker for Unifiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=None,
        help="并发数（默认从环境变量读取，通常为4）",
    )

    parser.add_argument(
        "--loglevel",
        "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别（默认: INFO）",
    )

    parser.add_argument(
        "--queues",
        "-Q",
        type=str,
        default=None,
        help="监听的队列（逗号分隔，默认: unifiles_default,unifiles_extraction）",
    )

    parser.add_argument(
        "--hostname",
        "-n",
        type=str,
        default=None,
        help="Worker 主机名（默认自动生成）",
    )

    parser.add_argument(
        "--pool",
        "-P",
        type=str,
        default="prefork",
        choices=["prefork", "solo", "eventlet", "gevent", "threads"],
        help="Worker 池类型（默认: prefork）",
    )

    parser.add_argument(
        "--autoscale",
        "-A",
        type=str,
        default=None,
        help="自动缩放配置（格式: max,min，如 10,3）",
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    # 加载配置
    config = CeleryConfig()

    # 构建 Worker 启动参数
    worker_args = ["worker"]

    # 并发数
    concurrency = args.concurrency or config.worker_concurrency
    worker_args.extend(["--concurrency", str(concurrency)])

    # 日志级别
    worker_args.extend(["--loglevel", args.loglevel])

    # 队列
    queues = args.queues or "unifiles_default,unifiles_extraction"
    worker_args.extend(["--queues", queues])

    # Worker 主机名
    if args.hostname:
        worker_args.extend(["--hostname", args.hostname])

    # Worker 池类型
    worker_args.extend(["--pool", args.pool])

    # 自动缩放
    if args.autoscale:
        worker_args.extend(["--autoscale", args.autoscale])

    # 其他推荐配置
    worker_args.extend(
        [
            "--max-tasks-per-child",
            "100",  # 每个 worker 处理 100 个任务后重启，防止内存泄漏
            "--time-limit",
            "600",  # 硬超时 10 分钟
            "--soft-time-limit",
            "570",  # 软超时 9.5 分钟
        ]
    )

    # 打印启动信息
    logger.info("=" * 80)
    logger.info("Starting Celery Worker for Unifiles")
    logger.info("=" * 80)
    logger.info(f"Broker URL: {config.broker_url}")
    logger.info(f"Result Backend: {config.result_backend}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Queues: {queues}")
    logger.info(f"Log Level: {args.loglevel}")
    logger.info(f"Pool Type: {args.pool}")
    if args.autoscale:
        logger.info(f"Autoscale: {args.autoscale}")
    logger.info("=" * 80)

    # 启动 Worker
    try:
        celery_app.worker_main(worker_args)
    except KeyboardInterrupt:
        logger.info("Shutting down Celery Worker...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Failed to start Celery Worker: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
