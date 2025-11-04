"""
统一配置管理 - 支持环境变量和运行时动态修改

配置优先级（从高到低）：
1. 运行时修改（存储在数据库/Redis）
2. 环境变量
3. .env文件
4. 默认值

特性：
- 使用Pydantic Settings自动从环境变量加载
- 支持运行时动态修改配置（通过ConfigStore）
- 配置变更事件通知
- 配置验证
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import asyncio
import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


# ===== 子配置类 =====

class DatabaseSettings(BaseSettings):
    """PostgreSQL 数据库配置"""
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口", ge=1, le=65535)
    database: str = Field(default="unifiles", description="数据库名称")
    user: str = Field(default="postgres", description="数据库用户")
    password: str = Field(default="postgres", description="数据库密码")
    min_pool_size: int = Field(default=2, description="最小连接池大小", ge=1, le=100)
    max_pool_size: int = Field(default=10, description="最大连接池大小", ge=1, le=100)
    command_timeout: int = Field(default=30, description="命令超时(秒)", ge=1, le=300)

    model_config = SettingsConfigDict(env_prefix="PG_")


class RedisSettings(BaseSettings):
    """Redis 配置"""
    host: str = Field(default="localhost", description="Redis主机")
    port: int = Field(default=6379, description="Redis端口", ge=1, le=65535)
    db: int = Field(default=0, description="Redis数据库编号", ge=0, le=15)
    password: Optional[str] = Field(default=None, description="Redis密码")
    max_connections: int = Field(default=50, description="最大连接数", ge=1, le=1000)
    socket_timeout: int = Field(default=5, description="Socket超时", ge=1, le=60)
    socket_connect_timeout: int = Field(default=5, description="连接超时", ge=1, le=60)

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class MinIOSettings(BaseSettings):
    """MinIO/S3 对象存储配置"""
    endpoint: str = Field(default="localhost:9000", description="MinIO端点")
    access_key: str = Field(default="minioadmin", description="Access Key")
    secret_key: str = Field(default="minioadmin", description="Secret Key")
    bucket_name: str = Field(default="unifiles", description="默认Bucket")
    secure: bool = Field(default=False, description="是否使用HTTPS")
    region: str = Field(default="us-east-1", description="区域")

    model_config = SettingsConfigDict(env_prefix="MINIO_")


class OpenTelemetrySettings(BaseSettings):
    """OpenTelemetry 追踪配置"""
    enabled: bool = Field(default=False, description="是否启用OTel")
    exporter_endpoint: str = Field(default="localhost:4317", description="OTLP端点")
    sampling_ratio: float = Field(default=1.0, description="采样率", ge=0.0, le=1.0)
    console_export: bool = Field(default=False, description="控制台导出")

    model_config = SettingsConfigDict(env_prefix="OTEL_")


class SecuritySettings(BaseSettings):
    """安全配置"""
    secret_key: str = Field(default="dev-secret-key-change-in-production-32-chars-min", description="应用密钥(用于加密)")
    api_key_hash_rounds: int = Field(default=12, description="API密钥Hash轮数", ge=10, le=15)
    password_hash_algorithm: str = Field(default="bcrypt", description="密码Hash算法")
    jwt_algorithm: str = Field(default="HS256", description="JWT算法")
    jwt_expiration_hours: int = Field(default=24, description="JWT过期时间", ge=1, le=720)

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret_key必须至少32个字符")
        return v


class CORSSettings(BaseSettings):
    """CORS 配置"""
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="允许的来源"
    )
    allow_credentials: bool = Field(default=True, description="允许凭据")
    allow_methods: List[str] = Field(default=["*"], description="允许的方法")
    allow_headers: List[str] = Field(default=["*"], description="允许的头部")

    model_config = SettingsConfigDict(env_prefix="CORS_")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# ===== 主配置类 =====

class Settings(BaseSettings):
    """
    主配置类 - 聚合所有配置

    支持从以下来源加载（优先级从高到低）：
    1. 运行时动态配置（ConfigStore）
    2. 环境变量
    3. .env文件
    4. 默认值
    """

    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # 应用配置
    app_name: str = Field(default="Unifiles", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    api_prefix: str = Field(default="/api/v1", description="API前缀")

    # 子配置（使用 default_factory 自动初始化）
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    otel: OpenTelemetrySettings = Field(default_factory=OpenTelemetrySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    # 功能开关（支持运行时修改）
    enable_quota_check: bool = Field(default=True, description="启用配额检查")
    enable_file_validation: bool = Field(default=True, description="启用文件验证")
    enable_webhooks: bool = Field(default=True, description="启用Webhook")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def pg_dsn(self) -> str:
        """PostgreSQL DSN"""
        return (
            f"postgresql://{self.database.user}:{self.database.password}"
            f"@{self.database.host}:{self.database.port}/{self.database.database}"
        )

    @property
    def redis_url(self) -> str:
        """Redis URL"""
        auth = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{auth}{self.redis.host}:{self.redis.port}/{self.redis.db}"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == "development"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return self.model_dump()


# ===== 运行时配置存储 =====

class ConfigStore:
    """
    配置存储 - 支持运行时动态修改配置

    配置存储在Redis中，支持：
    - 运行时修改配置项
    - 配置变更通知
    - 配置持久化

    使用示例：
    ```python
    config_store = await get_config_store()

    # 读取配置
    quota_enabled = await config_store.get("enable_quota_check", default=True)

    # 修改配置
    await config_store.set("enable_quota_check", False)

    # 监听配置变更
    def on_config_change(key, old_value, new_value):
        logger.info(f"Config {key} changed: {old_value} -> {new_value}")

    config_store.add_listener("enable_quota_check", on_config_change)
    ```
    """

    def __init__(self, redis_client=None, key_prefix: str = "config:"):
        """
        初始化配置存储

        Args:
            redis_client: Redis客户端（可选）
            key_prefix: Redis key前缀
        """
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._cache: Dict[str, Any] = {}
        self._listeners: Dict[str, List[Callable]] = {}
        self._initialized = False

    async def initialize(self, redis_client):
        """
        初始化配置存储

        Args:
            redis_client: Redis客户端
        """
        if self._initialized:
            return

        self._redis = redis_client
        self._initialized = True

        # 加载所有配置到缓存
        await self._load_all_configs()

        logger.info("ConfigStore initialized")

    async def _load_all_configs(self):
        """从Redis加载所有配置到缓存"""
        if not self._redis:
            return

        try:
            # 获取所有配置key
            pattern = f"{self._key_prefix}*"
            keys = []

            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key.decode() if isinstance(key, bytes) else key)

            # 批量加载配置值
            if keys:
                for key in keys:
                    value = await self._redis.get(key)
                    if value:
                        config_key = key.replace(self._key_prefix, "")
                        self._cache[config_key] = json.loads(
                            value.decode() if isinstance(value, bytes) else value
                        )

            logger.debug(f"Loaded {len(keys)} configs from Redis")

        except Exception as e:
            logger.warning(f"Failed to load configs from Redis: {e}")

    async def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        # 先从缓存获取
        if key in self._cache:
            return self._cache[key]

        # 从Redis获取
        if self._redis:
            try:
                redis_key = f"{self._key_prefix}{key}"
                value = await self._redis.get(redis_key)

                if value:
                    parsed_value = json.loads(
                        value.decode() if isinstance(value, bytes) else value
                    )
                    self._cache[key] = parsed_value
                    return parsed_value
            except Exception as e:
                logger.warning(f"Failed to get config '{key}' from Redis: {e}")

        return default

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            ttl: 过期时间（秒），None表示永久
        """
        old_value = self._cache.get(key)

        # 更新缓存
        self._cache[key] = value

        # 存储到Redis
        if self._redis:
            try:
                redis_key = f"{self._key_prefix}{key}"
                value_json = json.dumps(value)

                if ttl:
                    await self._redis.setex(redis_key, ttl, value_json)
                else:
                    await self._redis.set(redis_key, value_json)

                logger.info(f"Config '{key}' updated: {old_value} -> {value}")

            except Exception as e:
                logger.error(f"Failed to set config '{key}' in Redis: {e}")
                raise

        # 触发变更监听器
        await self._notify_listeners(key, old_value, value)

    async def delete(self, key: str):
        """删除配置"""
        if key in self._cache:
            old_value = self._cache.pop(key)

            if self._redis:
                redis_key = f"{self._key_prefix}{key}"
                await self._redis.delete(redis_key)

            await self._notify_listeners(key, old_value, None)

    def add_listener(self, key: str, callback: Callable):
        """
        添加配置变更监听器

        Args:
            key: 监听的配置键
            callback: 回调函数 (key, old_value, new_value) -> None
        """
        if key not in self._listeners:
            self._listeners[key] = []

        self._listeners[key].append(callback)
        logger.debug(f"Added listener for config '{key}'")

    async def _notify_listeners(self, key: str, old_value: Any, new_value: Any):
        """通知配置变更监听器"""
        if key in self._listeners:
            for callback in self._listeners[key]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(key, old_value, new_value)
                    else:
                        callback(key, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in config listener for '{key}': {e}")


# ===== 全局单例 =====

_settings: Optional[Settings] = None
_config_store: Optional[ConfigStore] = None


def get_settings() -> Settings:
    """
    获取全局Settings单例

    Settings在应用启动时创建，从环境变量和.env文件加载
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        logger.info(f"Settings loaded: environment={_settings.environment}")
    return _settings


async def get_config_store() -> ConfigStore:
    """
    获取全局ConfigStore单例

    ConfigStore用于运行时配置，需要在应用启动后初始化
    """
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore()
        logger.info("ConfigStore created (not initialized yet)")
    return _config_store


async def init_config_store(redis_client):
    """
    初始化ConfigStore

    应该在应用启动时调用，Redis连接建立后

    Args:
        redis_client: Redis客户端
    """
    config_store = await get_config_store()
    await config_store.initialize(redis_client)
    logger.success("ConfigStore initialized with Redis")


# 便捷访问
settings = get_settings()


# ===== 配置管理API辅助函数 =====

async def get_runtime_config(key: str, default: Any = None) -> Any:
    """
    获取运行时配置（优先从ConfigStore，否则从Settings）

    使用示例：
    ```python
    enable_quota = await get_runtime_config("enable_quota_check", default=True)
    ```
    """
    config_store = await get_config_store()

    # 先尝试从ConfigStore获取
    runtime_value = await config_store.get(key)
    if runtime_value is not None:
        return runtime_value

    # 否则从Settings获取
    if hasattr(settings, key):
        return getattr(settings, key)

    return default


async def set_runtime_config(key: str, value: Any):
    """
    设置运行时配置

    使用示例：
    ```python
    await set_runtime_config("enable_quota_check", False)
    ```
    """
    config_store = await get_config_store()
    await config_store.set(key, value)
