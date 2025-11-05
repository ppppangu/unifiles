"""
Unifiles 配置模块

提供类型安全的配置管理，使用 Pydantic Settings。

使用示例:
    from unifiles.config import settings

    # 访问配置
    db_host = settings.database.host
    redis_port = settings.redis.port

    # 运行时配置
    from unifiles.config import get_runtime_config, set_runtime_config

    quota_enabled = await get_runtime_config("enable_quota_check")
    await set_runtime_config("enable_quota_check", False)
"""

from .settings import (
    # Settings classes
    Settings,
    DatabaseSettings,
    RedisSettings,
    MinIOSettings,
    OpenTelemetrySettings,
    SecuritySettings,
    CORSSettings,
    # Singleton instance
    settings,
    get_settings,
    # Runtime configuration
    ConfigStore,
    get_config_store,
    init_config_store,
    get_runtime_config,
    set_runtime_config,
)

from .client_settings import (
    ClientSettings,
    get_client_settings,
    client_settings,
)

__all__ = [
    # Server settings classes
    "Settings",
    "DatabaseSettings",
    "RedisSettings",
    "MinIOSettings",
    "OpenTelemetrySettings",
    "SecuritySettings",
    "CORSSettings",
    # Global instance
    "settings",
    "get_settings",
    # Runtime config
    "ConfigStore",
    "get_config_store",
    "init_config_store",
    "get_runtime_config",
    "set_runtime_config",
    # Client settings
    "ClientSettings",
    "get_client_settings",
    "client_settings",
]
