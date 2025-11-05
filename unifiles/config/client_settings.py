"""
Unifiles 客户端配置

客户端配置优先级（从高到低）：
1. 显式传入的参数
2. 环境变量
3. .env文件
4. 默认值

使用示例:
    from unifiles.config import client_settings

    # 访问配置
    api_key = client_settings.api_key
    base_url = client_settings.base_url
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientSettings(BaseSettings):
    """
    客户端配置类

    配置优先级（从高到低）：
    1. 显式传入的参数（通过构造函数）
    2. 环境变量
    3. .env文件
    4. 默认值
    """

    # API 配置
    base_url: str = Field(
        default="http://localhost:8088",
        description="API基础URL"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API密钥"
    )
    timeout: int = Field(
        default=30,
        description="请求超时时间（秒）",
        ge=1,
        le=300
    )

    # 重试配置
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
        ge=0,
        le=10
    )
    retry_delay: float = Field(
        default=1.0,
        description="重试延迟（秒）",
        ge=0.1,
        le=60.0
    )

    # 连接池配置
    max_connections: int = Field(
        default=10,
        description="最大连接数",
        ge=1,
        le=100
    )

    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )
    enable_debug: bool = Field(
        default=False,
        description="启用调试模式"
    )

    model_config = SettingsConfigDict(
        env_prefix="UNIFILES_CLIENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# 全局单例
_client_settings: Optional[ClientSettings] = None


def get_client_settings() -> ClientSettings:
    """
    获取全局ClientSettings单例

    Returns:
        ClientSettings实例
    """
    global _client_settings
    if _client_settings is None:
        _client_settings = ClientSettings()
    return _client_settings


# 便捷访问
client_settings = get_client_settings()


__all__ = [
    "ClientSettings",
    "get_client_settings",
    "client_settings",
]
