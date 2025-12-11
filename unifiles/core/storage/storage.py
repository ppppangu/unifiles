"""
Storage orchestrator and backends.

本模块提供存储系统的核心功能：
- DatabaseBootstrapper: 启动时检查数据库 schema 是否存在
- BaseStorageBackend: 存储后端抽象基类
- LocalStorageBackend: 本地文件系统存储实现
- MinioStorageBackend: MinIO/S3 对象存储实现
- Storage: 存储编排器，管理多个后端并提供统一接口

使用方式：
    storage = await get_initialized_storage()
    backend = await storage.get_default_backend()
    await backend.upload_file("path/to/file.txt", content)

数据库初始化请使用: python scripts/init_db.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from unifiles.core.logging import get_logger


def _get_logger():
    """延迟获取 logger，避免在模块 import 时过早初始化"""
    return get_logger()


# 注意: 不在模块级别调用 _get_logger()，而是在需要时动态调用
from minio import Minio
from minio.error import S3Error

from unifiles.core.config.env_config import read_minio_config
from unifiles.core.config.models.connection_config import (
    LocalConnection,
    MinIOConnection,
)
from unifiles.core.config.models.storage_config import ConfigSource, StorageConfig


# =============================================================================
# 异常类
# =============================================================================


class StorageError(Exception):
    """存储操作通用异常"""


class StorageInitializationError(StorageError):
    """存储初始化失败时抛出"""


class DatabaseBootstrapper:
    """Checks PostgreSQL database/schema readiness at startup.

    Note: Actual database initialization is handled by `scripts/init_db.py`.
    This class only performs connectivity and schema existence checks.
    """

    def __init__(self):
        try:
            _get_logger().info("[DB] Bootstrapper initialized for schema check")
        except Exception:
            pass

    async def ensure_database_ready(self) -> None:
        """Ensure the database is reachable and schema exists.

        Uses the global connection pool (initialized in main.py) instead of
        creating standalone connections, ensuring resource reuse.
        """
        from unifiles.core.database import get_connection_pool

        _get_logger().info(
            "[DB] ensure_database_ready: checking schema via global pool"
        )
        try:
            pool = await get_connection_pool()

            async with pool.acquire() as conn:
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'unifiles')"
                )

            if schema_exists:
                _get_logger().info("[DB] Schema 'unifiles' exists; database ready")
                return

            _get_logger().warning(
                "[DB] Schema 'unifiles' not found. "
                "Please run: python scripts/init_db.py"
            )

        except Exception as exc:
            _get_logger().warning(
                f"Database connectivity check failed: {exc}. "
                "Service will continue without database features."
            )
            return

    async def health_check(self) -> Dict[str, Any]:
        """Return database health information."""
        from unifiles.core.database import get_connection_pool

        try:
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Check connectivity
                await conn.fetchval("SELECT 1")
                # Check schema
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'unifiles')"
                )

            if schema_exists:
                return {"status": "healthy"}
            return {"status": "degraded", "warning": "Schema 'unifiles' not found"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


# =============================================================================
# 存储后端基类与实现
# =============================================================================


class BaseStorageBackend:
    """存储后端抽象基类，定义统一接口。子类需实现具体的上传/删除/访问逻辑。"""

    def __init__(self, config: StorageConfig):
        self.config = config

    @property
    def backend_id(self) -> str:
        return self.config.id

    async def initialize(self) -> None:
        """Perform backend specific initialization (override if needed)."""

    async def upload_file(
        self,
        object_path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        raise NotImplementedError

    async def upload_file_from_path(
        self,
        object_path: str,
        local_file_path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        raise NotImplementedError

    async def delete_file(self, object_path: str) -> bool:
        raise NotImplementedError

    def get_access_url(
        self,
        object_path: str,
        access_type: str = "presigned",
        expires_in_hours: Optional[int] = 24,
    ) -> str:
        raise NotImplementedError

    def get_storage_type(self) -> str:
        return self.config.connection.provider.value

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "unknown"}

    def get_metrics(self) -> Dict[str, Any]:
        return {"storage_type": self.get_storage_type()}


class LocalStorageBackend(BaseStorageBackend):
    """本地文件系统存储后端。文件存储在 base_path 目录下，元数据以 .meta.json 后缀存储。"""

    def __init__(self, config: StorageConfig, connection: LocalConnection):
        super().__init__(config)
        self._connection = connection
        self._base_path = Path(connection.base_path)
        self._metadata_suffix = ".meta.json"

    async def initialize(self) -> None:  # pragma: no cover - trivial
        _get_logger().info("[LocalStorage] initialize: begin")
        await asyncio.to_thread(self._prepare_directory)
        _get_logger().info(
            f"[LocalStorage] initialize: directory ready at {self._base_path}"
        )

    def _prepare_directory(self) -> None:
        _get_logger().info(
            f"[LocalStorage] Preparing directory (path={self._base_path!s}, "
            f"create_if_missing={self._connection.create_if_missing})"
        )
        if self._connection.create_if_missing:
            self._base_path.mkdir(mode=0o755, parents=True, exist_ok=True)
        if not self._base_path.exists():
            raise StorageInitializationError(
                f"Local storage path does not exist: {self._base_path}"
            )

    async def upload_file(
        self,
        object_path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        destination = self._base_path / object_path
        await asyncio.to_thread(self._write_bytes, destination, content)

        if metadata:
            await asyncio.to_thread(
                self._write_metadata,
                destination.with_suffix(destination.suffix + self._metadata_suffix),
                metadata,
            )

        return object_path

    async def upload_file_from_path(
        self,
        object_path: str,
        local_file_path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        destination = self._base_path / object_path
        source = Path(local_file_path)
        if not source.exists():
            raise FileNotFoundError(f"Local file not found: {local_file_path}")

        await asyncio.to_thread(self._copy_file, source, destination)

        if metadata:
            await asyncio.to_thread(
                self._write_metadata,
                destination.with_suffix(destination.suffix + self._metadata_suffix),
                metadata,
            )

        return object_path

    async def delete_file(self, object_path: str) -> bool:
        destination = self._base_path / object_path
        deleted = await asyncio.to_thread(self._remove_file_if_exists, destination)
        meta_deleted = await asyncio.to_thread(
            self._remove_file_if_exists,
            destination.with_suffix(destination.suffix + self._metadata_suffix),
        )
        return deleted or meta_deleted

    def get_access_url(
        self,
        object_path: str,
        access_type: str = "presigned",
        expires_in_hours: Optional[int] = 24,
    ) -> str:  # pragma: no cover - simple formatting
        if self.config.public_url_prefix:
            return f"{self.config.public_url_prefix.rstrip('/')}/{object_path}"
        return (self._base_path / object_path).as_uri()

    async def health_check(self) -> Dict[str, Any]:
        def check() -> Dict[str, Any]:
            if not self._base_path.exists():
                return {"status": "error", "error": f"path missing: {self._base_path}"}
            if not os.access(self._base_path, os.W_OK):
                return {"status": "degraded", "warning": "path not writable"}
            return {"status": "healthy"}

        return await asyncio.to_thread(check)

    def get_metrics(self) -> Dict[str, Any]:
        total_files = 0
        total_bytes = 0

        for file_path in self._base_path.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith(
                self._metadata_suffix
            ):
                total_files += 1
                total_bytes += file_path.stat().st_size

        return {
            "storage_type": self.get_storage_type(),
            "base_path": str(self._base_path),
            "total_files": total_files,
            "total_bytes": total_bytes,
        }

    @staticmethod
    def _write_bytes(destination: Path, content: bytes) -> None:
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        destination.write_bytes(content)

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    @staticmethod
    def _write_metadata(meta_path: Path, metadata: Dict[str, Any]) -> None:
        meta_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _remove_file_if_exists(path: Path) -> bool:
        if path.exists():
            path.unlink()
            return True
        return False


class MinioStorageBackend(BaseStorageBackend):
    """MinIO/S3 对象存储后端。支持 presigned URL 和公开 URL 两种访问方式。"""

    def __init__(self, config: StorageConfig, connection: MinIOConnection):
        super().__init__(config)
        self._connection = connection
        _get_logger().info(
            f"[MinIO] Creating client (endpoint={connection.endpoint}, secure={connection.secure}, "
            f"bucket={connection.bucket_name})"
        )
        self._client = Minio(
            connection.endpoint,
            access_key=connection.access_key,
            secret_key=connection.secret_key,
            secure=connection.secure,
        )
        self._bucket_name = connection.bucket_name

    async def initialize(self) -> None:
        _get_logger().info(
            f"[MinIO] initialize: begin ensure bucket '{self._bucket_name}'"
        )
        await asyncio.to_thread(self._ensure_bucket_exists)
        _get_logger().info(f"[MinIO] initialize: bucket ensured '{self._bucket_name}'")

    def _ensure_bucket_exists(self) -> None:
        try:
            _get_logger().info(
                f"[MinIO] Checking if bucket exists: {self._bucket_name}"
            )
            if not self._client.bucket_exists(self._bucket_name):
                self._client.make_bucket(self._bucket_name)
                _get_logger().info(f"Created MinIO bucket: {self._bucket_name}")
        except S3Error as exc:
            raise StorageInitializationError(
                f"Failed to ensure MinIO bucket: {exc}"
            ) from exc

    async def upload_file(
        self,
        object_path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        data_stream = io.BytesIO(content)
        length = len(content)

        # Normalize user metadata to satisfy S3/MinIO ASCII-only requirements
        norm_metadata: Dict[str, str] = self._normalize_metadata(metadata or {})

        def put_object() -> str:
            self._client.put_object(
                self._bucket_name,
                object_path,
                data_stream,
                length,
                content_type=content_type,
                metadata=norm_metadata,
            )
            return object_path

        await asyncio.to_thread(put_object)
        return object_path

    async def upload_file_from_path(
        self,
        object_path: str,
        local_file_path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        file_path = Path(local_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_file_path}")

        # Normalize user metadata to satisfy S3/MinIO ASCII-only requirements
        norm_metadata: Dict[str, str] = self._normalize_metadata(metadata or {})

        def fput_object() -> str:
            self._client.fput_object(
                self._bucket_name,
                object_path,
                str(file_path),
                content_type=content_type,
                metadata=norm_metadata,
            )
            return object_path

        await asyncio.to_thread(fput_object)
        return object_path

    def _normalize_metadata(self, meta: Dict[str, Any]) -> Dict[str, str]:
        """Normalize user metadata to ASCII-only strings acceptable by S3/MinIO.

        - Converts keys to lowercase strings; non-ASCII keys are percent-encoded.
        - Converts values to strings; percent-encodes if non-ASCII.
        - Skips None values.
        """
        normalized: Dict[str, str] = {}
        for k, v in meta.items():
            if v is None:
                continue
            # Key normalization
            key_str = str(k).lower()
            try:
                key_str.encode("us-ascii")
            except Exception:
                key_str = quote(key_str, safe="-_.()")

            # Value normalization
            val_str = str(v)
            try:
                val_str.encode("us-ascii")
            except Exception:
                val_str = quote(val_str, safe="-_.()")

            normalized[key_str] = val_str
        return normalized

    async def delete_file(self, object_path: str) -> bool:
        def remove() -> bool:
            try:
                self._client.remove_object(self._bucket_name, object_path)
                return True
            except S3Error as exc:
                _get_logger().warning(
                    f"Failed to delete MinIO object {object_path}: {exc}"
                )
                return False

        return await asyncio.to_thread(remove)

    def get_access_url(
        self,
        object_path: str,
        access_type: str = "presigned",
        expires_in_hours: Optional[int] = 24,
    ) -> str:
        if access_type == "public" and self.config.public_url_prefix:
            return self.config.generate_public_url(object_path)

        expiry = timedelta(hours=expires_in_hours or 24)
        return self._client.presigned_get_object(
            self._bucket_name,
            object_path,
            expires=expiry,
        )

    async def health_check(self) -> Dict[str, Any]:
        def check() -> Dict[str, Any]:
            try:
                exists = self._client.bucket_exists(self._bucket_name)
                return {
                    "status": "healthy" if exists else "error",
                    "bucket": self._bucket_name,
                }
            except S3Error as exc:
                return {
                    "status": "error",
                    "error": str(exc),
                    "bucket": self._bucket_name,
                }

        return await asyncio.to_thread(check)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "storage_type": self.get_storage_type(),
            "bucket": self._bucket_name,
            "endpoint": self._connection.endpoint,
            "secure": self._connection.secure,
        }


# =============================================================================
# 存储编排器
# =============================================================================


@dataclass
class StorageState:
    """Storage 编排器的内部状态"""

    initialized: bool = False
    default_backend_id: str | None = None


class Storage:
    """
    存储编排器 - 管理多个存储后端，提供统一的存储访问接口。

    初始化流程 (由 main.py 调用):
    1. 检查数据库 schema 是否存在
    2. 加载存储配置 (MinIO + 本地存储)
    3. 初始化各个存储后端
    4. 设置默认后端
    """

    def __init__(self):
        self._state = StorageState()
        self._init_lock = asyncio.Lock()
        self._backends: dict[str, BaseStorageBackend] = {}
        self._db_bootstrapper = DatabaseBootstrapper()
        self._project_root = Path(__file__).resolve().parents[3]
        _get_logger().info(
            f"[Storage] Orchestrator created (project_root={self._project_root!s})"
        )

    async def initialize(self) -> None:
        """Initialize storage backends and ensure database readiness."""
        if self._state.initialized:
            _get_logger().info("[Storage] initialize: already initialized; skipping")
            return

        async with self._init_lock:
            if self._state.initialized:
                _get_logger().info(
                    "[Storage] initialize: already initialized (after lock)"
                )
                return

            _get_logger().info("[Storage] Initializing Storage orchestrator...")
            _get_logger().info("[Storage] Step 1/4: Ensuring database readiness")
            await self._db_bootstrapper.ensure_database_ready()

            _get_logger().info("[Storage] Step 2/4: Loading storage configs")
            configs = self._load_storage_configs()
            if not configs:
                raise StorageInitializationError("No storage configurations available")
            _get_logger().info(f"[Storage] Loaded {len(configs)} storage config(s)")

            _get_logger().info("[Storage] Step 3/4: Initializing backends")
            for config in configs:
                _get_logger().info(
                    f"[Storage] Preparing backend id={config.id} "
                    f"provider={getattr(config.connection.provider, 'value', 'unknown')} "
                    f"active={getattr(config, 'is_active', False)}"
                )
                backend = self._create_backend(config)
                try:
                    _get_logger().info(
                        f"[Storage] -> initializing backend '{config.id}'"
                    )
                    await backend.initialize()
                    _get_logger().info(
                        f"[Storage] -> backend '{config.id}' initialized OK"
                    )
                except Exception as exc:
                    _get_logger().error(
                        f"Failed to initialize storage backend {config.id} "
                        f"({config.connection.provider.value}): {exc}"
                    )
                    continue

                self._backends[config.id] = backend
                if config.is_active and self._state.default_backend_id is None:
                    self._state.default_backend_id = config.id

            if not self._backends:
                raise StorageInitializationError(
                    "Failed to initialize any storage backend"
                )

            # Allow overriding default backend through env
            default_backend_env = os.getenv("UNIFILES_STORAGE_DEFAULT_ID")
            if default_backend_env and default_backend_env in self._backends:
                self._state.default_backend_id = default_backend_env

            if not self._state.default_backend_id:
                # Fall back to the first backend in the registry
                self._state.default_backend_id = next(iter(self._backends))

            self._state.initialized = True
            _get_logger().info(
                f"[Storage] Step 4/4: Initialization complete. "
                f"Default backend='{self._state.default_backend_id}' (available={len(self._backends)})"
            )

    async def get_backend(self, backend_id: str) -> BaseStorageBackend:
        _get_logger().debug(f"[Storage] get_backend({backend_id})")
        await self.initialize()
        backend = self._backends.get(backend_id)
        if backend is None:
            raise StorageError(f"Storage backend not found: {backend_id}")
        return backend

    async def get_default_backend(self) -> BaseStorageBackend:
        _get_logger().debug("[Storage] get_default_backend()")
        await self.initialize()
        return await self.get_backend(self._state.default_backend_id)  # type: ignore[arg-type]

    async def health_check(self) -> Dict[str, Any]:
        await self.initialize()

        result: Dict[str, Any] = {"status": "healthy", "database": {}, "backends": {}}
        db_status = await self._db_bootstrapper.health_check()
        result["database"] = db_status
        if db_status.get("status") != "healthy":
            result["status"] = "degraded"

        for backend_id, backend in self._backends.items():
            backend_status = await backend.health_check()
            result["backends"][backend_id] = backend_status
            if (
                backend_status.get("status") != "healthy"
                and result["status"] == "healthy"
            ):
                result["status"] = "degraded"

        return result

    def get_storage_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        for backend_id, backend in self._backends.items():
            metrics[backend_id] = backend.get_metrics()
        return metrics

    def _load_storage_configs(self) -> List[StorageConfig]:
        """Load storage configurations from environment/defaults."""
        configs: List[StorageConfig] = []
        _get_logger().debug("[Storage] _load_storage_configs: begin")

        # Try to load MinIO configuration first (if fully provided)
        try:
            minio_env = read_minio_config()
            if minio_env.get("access_key") and minio_env.get("secret_key"):
                _get_logger().info(
                    f"[Storage] MinIO config detected (endpoint={minio_env.get('endpoint') or minio_env.get('address')}, "
                    f"bucket={minio_env.get('bucket_name')}, secure={minio_env.get('secure')})"
                )
                minio_config = StorageConfig.from_env_config(
                    minio_env, config_id="minio-default"
                )
                configs.append(minio_config)
        except Exception as exc:
            _get_logger().warning(f"Failed to load MinIO configuration: {exc}")

        # Always include a local fallback storage
        local_base_path = os.getenv(
            "UNIFILES_STORAGE_LOCAL_BASE_PATH",
            str(self._project_root / "storage_data"),
        )
        try:
            _get_logger().info(
                f"[Storage] Adding local storage fallback (base_path={local_base_path})"
            )
            local_connection = LocalConnection(
                base_path=str(Path(local_base_path).expanduser().resolve()),
                create_if_missing=True,
            )
            local_config = StorageConfig(
                id="default-local",
                name="Local Filesystem Storage",
                connection=local_connection,
                is_active=True,
                config_source=ConfigSource.ENV,
                public_url_prefix=os.getenv("UNIFILES_STORAGE_LOCAL_PUBLIC_URL"),
            )
            configs.append(local_config)
        except Exception as exc:
            _get_logger().error(f"Failed to prepare local storage configuration: {exc}")

        _get_logger().debug(
            f"[Storage] _load_storage_configs: done (count={len(configs)})"
        )
        return configs

    def _create_backend(self, config: StorageConfig) -> BaseStorageBackend:
        connection = config.connection
        if isinstance(connection, LocalConnection):
            return LocalStorageBackend(config, connection)
        if isinstance(connection, MinIOConnection):
            return MinioStorageBackend(config, connection)
        raise StorageInitializationError(
            f"Unsupported storage provider: {connection.provider.value}"
        )


# =============================================================================
# 全局单例访问
# =============================================================================

_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """获取 Storage 单例 (不触发初始化)"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance


async def get_initialized_storage() -> Storage:
    """获取已初始化的 Storage 单例 (推荐使用此方法)"""
    _get_logger().info("[Storage] get_initialized_storage(): ensure initialized")
    storage = get_storage()
    await storage.initialize()
    return storage
