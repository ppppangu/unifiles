import io
from datetime import timedelta
from typing import Optional

from loguru import logger
from minio import Minio

from server.core.utils.tools import read_minio_config


def detect_content_type(
    file_name: str, default: str = "application/octet-stream"
) -> str:
    """根据文件扩展名智能检测 Content-Type。

    参数:
        file_name: 文件名或路径, 用于提取扩展名
        default: 无法识别时返回的默认 Content-Type

    返回:
        合适的 MIME 类型字符串, 失败时返回 default
    """
    import mimetypes

    # 先使用标准库猜测
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type:
        return mime_type

    # 扩展自定义映射
    from pathlib import Path

    ext = Path(file_name).suffix.lower()

    custom_mapping = {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".yml": "application/x-yaml",
        ".yaml": "application/x-yaml",
    }

    return custom_mapping.get(ext, default)


class StorageManager:
    """一个用于管理MinIO对象存储的类"""

    def __init__(self):
        """初始化MinIO客户端"""
        self.config = read_minio_config()
        self.client = Minio(
            endpoint=(
                self.config["address"]
                if "address" in self.config
                else f"{self.config['host']}:{int(self.config['port'])}"
            ),
            access_key=self.config["access_key"],
            secret_key=self.config["secret_key"],
            secure=self.config.get("secure", False),
        )
        self.bucket_name = self.config["bucket_name"]
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """确保存储桶存在，如果不存在则创建。"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Successfully created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error checking or creating bucket: {e}")
            raise

    def upload_file(
        self,
        object_path: str,
        file_content: bytes,
        file_name: str,
        content_type: str | None,
    ) -> str:
        """
        上传文件到MinIO。

        :param object_path: 文件在存储桶中的完整路径。
        :param file_content: 文件的二进制内容。
        :param file_name: 原始文件名，用于检测MIME类型。
        :param content_type: 文件的MIME类型。
        :return: 文件的对象路径（不再返回静态URL）。
        """
        try:
            file_size = len(file_content)

            if not content_type or content_type == "application/octet-stream":
                content_type = detect_content_type(file_name)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_path,
                data=io.BytesIO(file_content),
                length=file_size,
                content_type=content_type,
                part_size=10 * 1024 * 1024,  # 10MB part size
            )
            logger.info(f"File uploaded successfully to MinIO: {object_path}")
            return object_path

        except Exception as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            raise

    def generate_presigned_url(
        self,
        object_path: str,
        expires_in_hours: int = 24,
        response_headers: Optional[dict] = None,
    ) -> str:
        """
        生成预签名URL用于安全访问文件。

        :param object_path: 文件在存储桶中的路径
        :param expires_in_hours: URL过期时间（小时）
        :param response_headers: 响应头设置
        :return: 预签名URL
        """
        try:
            expires = timedelta(hours=expires_in_hours)

            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_path,
                expires=expires,
                response_headers=response_headers,
            )

            logger.debug(
                f"Generated presigned URL for {object_path}, expires in {expires_in_hours} hours"
            )
            return url

        except Exception as e:
            logger.error(f"Error generating presigned URL for {object_path}: {e}")
            raise

    def generate_public_url(self, object_path: str) -> str:
        """
        生成公共访问URL（如果配置了公共访问）。

        :param object_path: 文件在存储桶中的路径
        :return: 公共访问URL
        """
        try:
            if self.config.get("use_public_url") and self.config.get(
                "public_url_prefix"
            ):
                public_url = f"{self.config['public_url_prefix']}/{self.bucket_name}/{object_path}"
            else:
                endpoint = (
                    self.config.get("address")
                    or f"{self.config['host']}:{self.config['port']}"
                )
                public_url = f"http://{endpoint}/{self.bucket_name}/{object_path}"

            logger.debug(f"Generated public URL: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Error generating public URL for {object_path}: {e}")
            raise

    def get_file_access_url(
        self, object_path: str, access_type: str = "presigned", **kwargs
    ) -> str:
        """
        根据访问类型生成文件访问URL。

        :param object_path: 文件路径
        :param access_type: 访问类型 ('presigned' 或 'public')
        :param kwargs: 额外参数（如expires_in_hours等）
        :return: 访问URL
        """
        if access_type == "presigned":
            expires_in_hours = kwargs.get("expires_in_hours", 24)
            response_headers = kwargs.get("response_headers")
            return self.generate_presigned_url(
                object_path, expires_in_hours, response_headers
            )
        elif access_type == "public":
            return self.generate_public_url(object_path)
        else:
            raise ValueError(f"Unsupported access type: {access_type}")

    def delete_file(self, object_path: str):
        """从MinIO删除文件。"""
        try:
            self.client.remove_object(self.bucket_name, object_path)
            logger.info(f"File deleted from MinIO: {object_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file from MinIO, but proceeding: {e}")

    def file_exists(self, object_path: str) -> bool:
        """
        检查文件是否存在。

        :param object_path: 文件路径
        :return: 文件是否存在
        """
        try:
            self.client.stat_object(self.bucket_name, object_path)
            return True
        except Exception:
            return False

    def get_file_info(self, object_path: str) -> dict:
        """
        获取文件信息。

        :param object_path: 文件路径
        :return: 文件信息字典
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_path)
            return {
                "object_name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata,
            }
        except Exception as e:
            logger.error(f"Error getting file info for {object_path}: {e}")
            raise


# 创建一个可以被应用全局使用的实例
storage_manager = StorageManager()
