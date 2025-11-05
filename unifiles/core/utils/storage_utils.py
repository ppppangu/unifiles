"""
存储工具函数

提供MinIO和其他存储系统相关的工具函数。
"""

from loguru import logger


def convert_to_internal_minio_url(url: str, public_url_prefix: str = "", internal_endpoint: str = "localhost:9000") -> str:
    """
    将 MinIO 公网 URL 转换为内网 URL

    Args:
        url: MinIO 公网 URL
        public_url_prefix: 公网URL前缀（可选，如果不提供则从settings读取）
        internal_endpoint: 内网端点（可选，如果不提供则从settings读取）

    Returns:
        内网 URL 或原 URL（如果不需要转换）
    """
    try:
        # 如果未提供配置，从settings读取
        if not public_url_prefix or not internal_endpoint:
            from unifiles.config import settings

            # 尝试从settings获取public_url_prefix（如果未来添加此字段）
            # 目前MinIOSettings没有public_url_prefix，所以使用endpoint
            internal_endpoint = settings.minio.endpoint

            # 构建public URL (如果配置了secure，使用https)
            protocol = "https" if settings.minio.secure else "http"
            if not public_url_prefix:
                # 如果没有显式的公网前缀，假设公网地址与endpoint相同
                public_url_prefix = f"{protocol}://{settings.minio.endpoint}"

        if public_url_prefix and url.startswith(public_url_prefix):
            # 将公网前缀替换为内网地址
            internal_url = url.replace(public_url_prefix, f"http://{internal_endpoint}")
            logger.debug(f"Converted URL: {url} -> {internal_url}")
            return internal_url

        return url
    except Exception as e:
        logger.warning(f"Failed to convert MinIO URL: {e}")
        return url
