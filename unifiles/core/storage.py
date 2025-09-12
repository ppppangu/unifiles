import io

from loguru import logger
from minio import Minio

from server.core.utils.tools import detect_content_type, read_minio_config


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
        上传文件到MinIO并返回公共URL。

        :param object_path: 文件在存储桶中的完整路径。
        :param file_content: 文件的二进制内容。
        :param file_name: 原始文件名，用于检测MIME类型。
        :param content_type: 文件的MIME类型。
        :return: 文件的公共访问URL。
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

            if self.config.get("use_public_url") and self.config.get(
                "public_url_prefix"
            ):
                public_url = (
                    f"{self.config['public_url_prefix']}/{self.bucket_name}/{object_path}"
                )
            else:
                endpoint = (
                    self.config.get("address")
                    or f"{self.config['host']}:{self.config['port']}"
                )
                public_url = f"http://{endpoint}/{self.bucket_name}/{object_path}"

            logger.info(f"Generated public URL: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            raise

    def delete_file(self, object_path: str):
        """从MinIO删除文件。"""
        try:
            self.client.remove_object(self.bucket_name, object_path)
            logger.info(f"File deleted from MinIO: {object_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file from MinIO, but proceeding: {e}")


# 创建一个可以被应用全局使用的实例
storage_manager = StorageManager()
