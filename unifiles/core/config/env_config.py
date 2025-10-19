"""
新的环境变量配置管理模块
支持从 .env 文件和环境变量读取配置
配置优先级：.env 文件 > 环境变量 > 默认值
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


class EnvironmentConfig:
    """环境变量配置管理器"""

    def __init__(self, env_file_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            env_file_path: .env 文件路径，如果为None则使用项目根目录的.env文件
        """
        self._config_cache = {}
        self._env_loaded = False

        if env_file_path is None:
            # 默认使用项目根目录的 .env 文件
            project_root = Path(__file__).parent.parent.parent.parent
            env_file_path = project_root / ".env"

        self.env_file_path = Path(env_file_path)
        self._load_env_file()

    def _load_env_file(self):
        """加载 .env 文件"""
        if self._env_loaded:
            return

        if load_dotenv is None:
            logger.warning("python-dotenv not installed, .env file will not be loaded")
            return

        if self.env_file_path.exists():
            load_dotenv(self.env_file_path)
            logger.info(f"Loaded environment variables from {self.env_file_path}")
        else:
            logger.info(
                f".env file not found at {self.env_file_path}, using environment variables only"
            )

        self._env_loaded = True

    def get_env_value(
        self, key: str, default: Any = None, cast_type: type = str
    ) -> Any:
        """
        获取环境变量值

        Args:
            key: 环境变量键名
            default: 默认值
            cast_type: 转换类型 (str, int, float, bool)

        Returns:
            环境变量值
        """
        value = os.getenv(key, default)

        if value is None:
            return default

        # 如果是字符串默认值且环境变量也是字符串，直接返回
        if cast_type == str:
            return value

        # 类型转换
        try:
            if cast_type == bool:
                return value.lower() in ("true", "1", "yes", "on")
            if cast_type == int:
                return int(value)
            if cast_type == float:
                return float(value)
            return cast_type(value)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to convert {key}={value} to {cast_type.__name__}: {e}"
            )
            return default

    def get_api_instances(self, api_type: str) -> List[Dict[str, Any]]:
        """
        获取API实例配置

        Args:
            api_type: API类型 ('LANG_EMBED', 'MULTIMODAL', 'LANG_LLM')

        Returns:
            API实例配置列表
        """
        instances = []
        index = 0

        while True:
            name_key = f"UNIFILES_API_{api_type}_{index}_NAME"
            name = self.get_env_value(name_key)

            if not name:
                break

            instance = {
                "name": name,
                "url": self.get_env_value(f"UNIFILES_API_{api_type}_{index}_URL"),
                "key": self.get_env_value(f"UNIFILES_API_{api_type}_{index}_KEY", ""),
                "alias": self.get_env_value(
                    f"UNIFILES_API_{api_type}_{index}_ALIAS", ""
                ),
            }

            instances.append(instance)
            index += 1

        return instances

    def get_postgres_config(self) -> Dict[str, Any]:
        """获取PostgreSQL配置"""
        config = {
            "address": self.get_env_value(
                "UNIFILES_DB_POSTGRES_ADDRESS", "localhost:5432"
            ),
            "user": self.get_env_value("UNIFILES_DB_POSTGRES_USER", "postgres"),
            "password": self.get_env_value("UNIFILES_DB_POSTGRES_PASSWORD", "postgres"),
            "database": self.get_env_value("UNIFILES_DB_POSTGRES_DATABASE", "postgres"),
            "active": self.get_env_value("UNIFILES_DB_POSTGRES_ACTIVE", True, bool),
        }

        # 解析address字段为host和port
        if "address" in config:
            address = config["address"]
            if ":" in address:
                host, port = address.rsplit(":", 1)
                config["host"] = host
                config["port"] = int(port)
            else:
                config["host"] = address
                config["port"] = 5432

        return config

    def get_minio_config(self) -> Dict[str, Any]:
        """获取MinIO配置"""
        config = {
            "address": self.get_env_value(
                "UNIFILES_STORAGE_MINIO_ADDRESS", "localhost:9000"
            ),
            "access_key": self.get_env_value("UNIFILES_STORAGE_MINIO_ACCESS_KEY"),
            "secret_key": self.get_env_value("UNIFILES_STORAGE_MINIO_SECRET_KEY"),
            "bucket_name": self.get_env_value(
                "UNIFILES_STORAGE_MINIO_BUCKET_NAME", "unifiles"
            ),
            "region": self.get_env_value("UNIFILES_STORAGE_MINIO_REGION", "us-east-1"),
            "public_url_prefix": self.get_env_value(
                "UNIFILES_STORAGE_MINIO_PUBLIC_URL_PREFIX", ""
            ),
        }

        # 解析address字段为host和port（为了向后兼容）
        if "address" in config:
            address = config["address"]
            # Check if this is a full URL (contains ://)
            if "://" in address:
                # For full URLs like https://example.com/path, use as endpoint
                config["endpoint"] = address
                # Extract host for backward compatibility
                from urllib.parse import urlparse
                parsed = urlparse(address)
                config["host"] = parsed.netloc
                config["port"] = parsed.port or (443 if parsed.scheme == "https" else 80)
                config["secure"] = parsed.scheme == "https"
            elif ":" in address:
                # Traditional host:port format
                try:
                    host, port = address.rsplit(":", 1)
                    config["host"] = host
                    config["port"] = int(port)
                    config["endpoint"] = address
                    config["secure"] = False
                except ValueError:
                    # Fallback if port is not a number
                    config["host"] = address
                    config["port"] = 9000
                    config["endpoint"] = address
                    config["secure"] = False
            else:
                # Just hostname
                config["host"] = address
                config["port"] = 9000
                config["endpoint"] = address
                config["secure"] = False

        return config

    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置"""
        return {
            "default_storage_id": self.get_env_value("UNIFILES_STORAGE_DEFAULT_ID", "default-minio"),
            "default_fallback_strategy": self.get_env_value("UNIFILES_STORAGE_DEFAULT_FALLBACK", "fail_fast")  # or "use_first_active"
        }

    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        redis_url = self.get_env_value("UNIFILES_REDIS_URL", "redis://localhost:6379")

        # 如果提供了完整URL，直接使用
        if redis_url.startswith("redis://") or redis_url.startswith("rediss://"):
            return {
                "url": redis_url,
                "max_connections": self.get_env_value("UNIFILES_REDIS_MAX_CONNECTIONS", 50, int),
                "decode_responses": True,
                "encoding": "utf-8",
                # 连接池配置
                "socket_timeout": self.get_env_value("UNIFILES_REDIS_SOCKET_TIMEOUT", 5, int),
                "socket_connect_timeout": self.get_env_value("UNIFILES_REDIS_CONNECT_TIMEOUT", 5, int),
                "socket_keepalive": self.get_env_value("UNIFILES_REDIS_KEEPALIVE", True, bool),
                # 重试配置
                "retry_on_timeout": self.get_env_value("UNIFILES_REDIS_RETRY_ON_TIMEOUT", True, bool),
                "health_check_interval": self.get_env_value("UNIFILES_REDIS_HEALTH_CHECK_INTERVAL", 30, int),
            }

        # 否则使用主机和端口构建配置
        address = self.get_env_value("UNIFILES_REDIS_ADDRESS", "localhost:6379")
        if ":" in address:
            host, port = address.rsplit(":", 1)
        else:
            host, port = address, 6379

        return {
            "host": host,
            "port": int(port),
            "password": self.get_env_value("UNIFILES_REDIS_PASSWORD"),
            "db": self.get_env_value("UNIFILES_REDIS_DB", 0, int),
            "max_connections": self.get_env_value("UNIFILES_REDIS_MAX_CONNECTIONS", 50, int),
            "decode_responses": True,
            "encoding": "utf-8",
            # 连接池配置
            "socket_timeout": self.get_env_value("UNIFILES_REDIS_SOCKET_TIMEOUT", 5, int),
            "socket_connect_timeout": self.get_env_value("UNIFILES_REDIS_CONNECT_TIMEOUT", 5, int),
            "socket_keepalive": self.get_env_value("UNIFILES_REDIS_KEEPALIVE", True, bool),
            # 重试配置
            "retry_on_timeout": self.get_env_value("UNIFILES_REDIS_RETRY_ON_TIMEOUT", True, bool),
            "health_check_interval": self.get_env_value("UNIFILES_REDIS_HEALTH_CHECK_INTERVAL", 30, int),
        }

    def get_convert_servers(self) -> List[Dict[str, Any]]:
        """获取格式转换服务器配置"""
        servers = []
        index = 0

        while True:
            url_key = f"UNIFILES_SERVICE_CONVERT_{index}_URL"
            url = self.get_env_value(url_key)

            if not url:
                break

            server = {
                "url": url,
                "active": self.get_env_value(
                    f"UNIFILES_SERVICE_CONVERT_{index}_ACTIVE", True, bool
                ),
            }

            servers.append(server)
            index += 1

        return servers

    def get_ocr_mineru_servers(self) -> List[Dict[str, Any]]:
        """获取OCR Mineru服务器配置"""
        servers = []
        index = 0

        while True:
            url_key = f"UNIFILES_SERVICE_OCR_MINERU_{index}_URL"
            url = self.get_env_value(url_key)

            if not url:
                break

            server = {
                "url": url,
                "active": self.get_env_value(
                    f"UNIFILES_SERVICE_OCR_MINERU_{index}_ACTIVE", True, bool
                ),
            }

            servers.append(server)
            index += 1

        return servers

    def get_ocr_mistral_servers(self) -> List[Dict[str, Any]]:
        """获取OCR Mistral服务器配置"""
        servers = []
        index = 0

        while True:
            url_key = f"UNIFILES_SERVICE_OCR_MISTRAL_{index}_URL"
            url = self.get_env_value(url_key)

            if not url:
                break

            server = {
                "url": url,
                "api_key": self.get_env_value(
                    f"UNIFILES_SERVICE_OCR_MISTRAL_{index}_API_KEY", ""
                ),
                "active": self.get_env_value(
                    f"UNIFILES_SERVICE_OCR_MISTRAL_{index}_ACTIVE", True, bool
                ),
            }

            servers.append(server)
            index += 1

        return servers

    def get_text_chunk_strategy(self) -> Dict[str, Any]:
        """获取文本分块策略配置"""
        strategy_type = self.get_env_value(
            "UNIFILES_STRATEGY_TEXT_CHUNK_TYPE", "SlidingWindow"
        )

        return {
            strategy_type: {
                "module": self.get_env_value(
                    "UNIFILES_STRATEGY_TEXT_CHUNK_MODULE", "normal"
                ),
                "chunk_size": self.get_env_value(
                    "UNIFILES_STRATEGY_TEXT_CHUNK_SIZE", 800, int
                ),
                "chunk_overlap": self.get_env_value(
                    "UNIFILES_STRATEGY_TEXT_CHUNK_OVERLAP", 128, int
                ),
            }
        }

    def get_config(self) -> Dict[str, Any]:
        """
        获取完整的配置字典，兼容原始的config.yaml格式

        Returns:
            完整的配置字典
        """
        if "full_config" in self._config_cache:
            return self._config_cache["full_config"]

        config = {
            "api": {
                "language_embedding": self.get_api_instances("LANG_EMBED"),
                "multimodal_llm": self.get_api_instances("MULTIMODAL"),
                "language_llm": self.get_api_instances("LANG_LLM"),
            },
            "server_components": {
                "postgres": self.get_postgres_config(),
                "minio": self.get_minio_config(),
            },
            "convert_format_server": self.get_convert_servers(),
            "ocr": {
                "mineru": self.get_ocr_mineru_servers(),
                "mistral": self.get_ocr_mistral_servers(),
            },
            "text_chunk_strategy": self.get_text_chunk_strategy(),
        }

        self._config_cache["full_config"] = config
        return config


# 全局配置实例
_env_config: Optional[EnvironmentConfig] = None


def get_env_config() -> EnvironmentConfig:
    """获取全局环境配置实例（单例模式）"""
    global _env_config
    if _env_config is None:
        _env_config = EnvironmentConfig()
    return _env_config


def read_config() -> Dict[str, Any]:
    """
    新的配置读取函数，替代原来的 yaml 配置读取
    保持与原有代码的兼容性
    """
    env_config = get_env_config()
    return env_config.get_config()


def read_pg_config() -> Dict[str, Any]:
    """读取PostgreSQL配置（兼容性函数）"""
    env_config = get_env_config()
    return env_config.get_postgres_config()


def read_minio_config() -> Dict[str, Any]:
    """读取MinIO配置（兼容性函数）"""
    env_config = get_env_config()
    return env_config.get_minio_config()


def read_redis_config() -> Dict[str, Any]:
    """读取Redis配置（兼容性函数）"""
    env_config = get_env_config()
    return env_config.get_redis_config()


def convert_to_internal_minio_url(url: str) -> str:
    """
    将 MinIO 公网 URL 转换为内网 URL

    Args:
        url: MinIO 公网 URL

    Returns:
        内网 URL 或原 URL（如果不需要转换）
    """
    try:
        minio_config = read_minio_config()
        public_url_prefix = minio_config.get("public_url_prefix", "")

        if public_url_prefix and url.startswith(public_url_prefix):
            # 将公网前缀替换为内网地址
            internal_address = minio_config.get("address", "localhost:9000")
            internal_url = url.replace(public_url_prefix, f"http://{internal_address}")
            return internal_url

        return url
    except Exception as e:
        logger.warning(f"Failed to convert MinIO URL: {e}")
        return url


# ======================================
# ===========  目录管理工具 =============
# ======================================


def mk_logs_path() -> None:
    """创建日志目录"""
    from pathlib import Path

    log_path = Path(__file__).parent.parent.parent / "logs"
    log_path.mkdir(mode=0o777, exist_ok=True)


def mk_temp_path() -> None:
    """创建临时目录"""
    from pathlib import Path

    temp_path = Path(__file__).parent.parent.parent / "tmp"
    temp_path.mkdir(mode=0o777, exist_ok=True)


def mk_need_path() -> None:
    """创建必要目录"""
    mk_logs_path()
    mk_temp_path()
