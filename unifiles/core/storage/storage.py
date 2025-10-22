"""
Storage orchestrator and backends.

Provides the `Storage` coordinator used across the application to interact with
object storage providers while ensuring that the backing PostgreSQL database is
ready (schema present and baseline objects created).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

try:
    # Bind service name so logs pass Loguru filter configured by init_logger
    logger = logger.bind(service="unifiles-v1")
except Exception:
    # Fallback: if binding fails for any reason, keep default logger
    pass
from minio import Minio
from minio.error import S3Error
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from unifiles.core.config.env_config import read_minio_config, read_pg_config
from unifiles.core.config.models.connection_config import (
    LocalConnection,
    MinIOConnection,
)
from unifiles.core.config.models.storage_config import ConfigSource, StorageConfig


class StorageError(Exception):
    """Generic storage error."""


class StorageInitializationError(StorageError):
    """Raised when storage cannot be initialized."""


class DatabaseBootstrapper:
    """Ensures the PostgreSQL database/schema required by the service exists."""

    SQL_FILE_ORDER: Iterable[str] = (
        "011-create-extensions.sql",
        "021-create-users.sql",
        "022-create-access-key-management.sql",
        "031-create-file-management.sql",
        "041-create-content-extraction.sql",
        "051-create-knowledge-base.sql",
        "061-create-component-abstraction.sql",
        # "071-create-indexes.sql",
        "081-create-triggers.sql",
    )

    REQUIRED_RELATIONS: Iterable[str] = (
        "unifiles.users",
        "unifiles.files",
        "unifiles.documents",
        "unifiles.knowledge_bases",
    )

    def __init__(self, sql_dir: Optional[Path] = None):
        self._pg_config = read_pg_config()
        self._sql_dir = (
            sql_dir or Path(__file__).resolve().parents[3] / "scripts" / "sql"
        )
        try:
            logger.info(
                "[DB] Bootstrapper initialized (host=%s, port=%s, db=%s, sql_dir=%s)",
                self._pg_config.get("host"),
                self._pg_config.get("port"),
                self._pg_config.get("database"),
                str(self._sql_dir),
            )
        except Exception:
            pass

    def _build_engine(self) -> Engine:
        """Create a SQLAlchemy engine for the configured database."""
        try:
            url = URL.create(
                drivername="postgresql+psycopg",
                username=self._pg_config.get("user"),
                password=self._pg_config.get("password"),
                host=self._pg_config.get("host"),
                port=int(self._pg_config.get("port", 5432)),
                database=self._pg_config.get("database", "postgres"),
            )
        except Exception as exc:  # pragma: no cover - configuration errors
            raise StorageInitializationError(
                f"Invalid PostgreSQL configuration: {exc}"
            ) from exc

        # 添加连接超时和池配置，加快启动速度
        logger.info(
            "[DB] Creating SQLAlchemy engine (host=%s, port=%s, db=%s)",
            self._pg_config.get("host"),
            self._pg_config.get("port"),
            self._pg_config.get("database"),
        )
        return create_engine(
            url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 5,  # 5秒连接超时
            },
            pool_size=5,
            max_overflow=10,
            pool_timeout=10,  # 10秒池超时
        )

    async def ensure_database_ready(self) -> None:
        """Ensure the database is reachable and schema exists."""
        # 使用asyncpg直接测试连接，避免SQLAlchemy连接池问题
        logger.info("[DB] ensure_database_ready: begin connectivity check via asyncpg")
        try:
            import asyncpg

            conn = await asyncpg.connect(
                host=self._pg_config.get("host"),
                port=int(self._pg_config.get("port", 5432)),
                user=self._pg_config.get("user"),
                password=self._pg_config.get("password"),
                database=self._pg_config.get("database", "postgres"),
                timeout=5,
            )
            logger.info("[DB] asyncpg connected successfully")
            # 快速检查schema是否存在
            schema_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'unifiles')"
            )
            await conn.close()

            if schema_exists:
                logger.info(
                    "[DB] Schema 'unifiles' exists; skipping bootstrap initialization"
                )
                return
            logger.warning("[DB] Schema 'unifiles' not found; may need initialization")
        # 如果需要，可以在这里调用同步初始化
        # await asyncio.to_thread(self._ensure_database_ready_sync)

        except Exception as exc:
            logger.warning(
                f"Database connectivity check failed: {exc}. "
                "Service will continue without database features."
            )
            return

    def _ensure_database_ready_sync(self) -> None:
        logger.info("[DB] _ensure_database_ready_sync: begin")
        engine = self._build_engine()
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("[DB] Engine connectivity check OK")
        except SQLAlchemyError as exc:
            logger.warning(
                f"Database connectivity check failed: {exc}. "
                "Service will continue without database features."
            )
            # 不抛出异常，允许服务继续启动（使用本地存储）
            return

        missing_relations: List[str] = []
        try:
            with engine.connect() as conn:
                missing_relations = self._detect_missing_relations(conn)
                logger.info(
                    "[DB] Missing relations detected: %s",
                    ", ".join(missing_relations) if missing_relations else "<none>",
                )
        except SQLAlchemyError as exc:
            raise StorageInitializationError(
                f"Failed to inspect database schema: {exc}"
            ) from exc

        if not missing_relations:
            logger.info("Database schema already present; skipping bootstrap scripts.")
            return

        logger.info(
            "Database schema incomplete (missing: %s). Running bootstrap scripts.",
            ", ".join(missing_relations),
        )

        try:
            with engine.begin() as conn:
                self._run_bootstrap_scripts(conn)
                logger.info("[DB] Bootstrap SQL scripts executed")
        except SQLAlchemyError as exc:
            raise StorageInitializationError(
                f"Failed to execute bootstrap scripts: {exc}"
            ) from exc

        logger.info("Database bootstrap scripts executed successfully.")

    def _detect_missing_relations(self, conn) -> List[str]:
        """Return a list of required relations that are missing."""
        missing: List[str] = []
        for relation in self.REQUIRED_RELATIONS:
            result = conn.execute(text("SELECT to_regclass(:name)"), {"name": relation})
            if result.scalar() is None:
                missing.append(relation)
        return missing

    def _run_bootstrap_scripts(self, conn) -> None:
        """Execute ordered SQL files to create the schema."""
        for filename in self.SQL_FILE_ORDER:
            sql_path = self._sql_dir / filename
            if not sql_path.exists():
                logger.warning("SQL bootstrap file missing: %s", sql_path)
                continue

            script = sql_path.read_text(encoding="utf-8")
            # psycopg treats '%' as placeholder marker; escape literal percent signs
            script = script.replace("%", "%%")

            logger.info("Executing bootstrap script: %s", filename)
            conn.exec_driver_sql(script)

    async def health_check(self) -> Dict[str, Any]:
        """Return database health information."""
        return await asyncio.to_thread(self._health_check_sync)

    def _health_check_sync(self) -> Dict[str, Any]:
        engine = self._build_engine()
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                missing = self._detect_missing_relations(conn)
        except SQLAlchemyError as exc:
            return {"status": "error", "error": str(exc)}

        status = "healthy" if not missing else "degraded"
        response: Dict[str, Any] = {"status": status}
        if missing:
            response["missing_relations"] = missing
        return response


class BaseStorageBackend:
    """Common interface for storage backends."""

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
    """Simple filesystem-based storage backend."""

    def __init__(self, config: StorageConfig, connection: LocalConnection):
        super().__init__(config)
        self._connection = connection
        self._base_path = Path(connection.base_path)
        self._metadata_suffix = ".meta.json"

    async def initialize(self) -> None:  # pragma: no cover - trivial
        logger.info("[LocalStorage] initialize: begin")
        await asyncio.to_thread(self._prepare_directory)
        logger.info("[LocalStorage] initialize: directory ready at %s", self._base_path)

    def _prepare_directory(self) -> None:
        logger.info(
            "[LocalStorage] Preparing directory (path=%s, create_if_missing=%s)",
            str(self._base_path),
            self._connection.create_if_missing,
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
    """MinIO storage backend implementation."""

    def __init__(self, config: StorageConfig, connection: MinIOConnection):
        super().__init__(config)
        self._connection = connection
        logger.info(
            "[MinIO] Creating client (endpoint=%s, secure=%s, bucket=%s)",
            connection.endpoint,
            connection.secure,
            connection.bucket_name,
        )
        self._client = Minio(
            connection.endpoint,
            access_key=connection.access_key,
            secret_key=connection.secret_key,
            secure=connection.secure,
        )
        self._bucket_name = connection.bucket_name

    async def initialize(self) -> None:
        logger.info("[MinIO] initialize: begin ensure bucket '%s'", self._bucket_name)
        await asyncio.to_thread(self._ensure_bucket_exists)
        logger.info("[MinIO] initialize: bucket ensured '%s'", self._bucket_name)

    def _ensure_bucket_exists(self) -> None:
        try:
            logger.info("[MinIO] Checking if bucket exists: %s", self._bucket_name)
            if not self._client.bucket_exists(self._bucket_name):
                self._client.make_bucket(self._bucket_name)
                logger.info("Created MinIO bucket: %s", self._bucket_name)
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

        def put_object() -> str:
            self._client.put_object(
                self._bucket_name,
                object_path,
                data_stream,
                length,
                content_type=content_type,
                metadata=metadata or {},
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

        def fput_object() -> str:
            self._client.fput_object(
                self._bucket_name,
                object_path,
                str(file_path),
                content_type=content_type,
                metadata=metadata or {},
            )
            return object_path

        await asyncio.to_thread(fput_object)
        return object_path

    async def delete_file(self, object_path: str) -> bool:
        def remove() -> bool:
            try:
                self._client.remove_object(self._bucket_name, object_path)
                return True
            except S3Error as exc:
                logger.warning("Failed to delete MinIO object %s: %s", object_path, exc)
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


@dataclass
class StorageState:
    """Internal state holder for the Storage orchestrator."""

    initialized: bool = False
    default_backend_id: str | None = None


class Storage:
    """Storage orchestrator managing available backends and database readiness."""

    def __init__(self):
        self._state = StorageState()
        self._init_lock = asyncio.Lock()
        self._backends: dict[str, BaseStorageBackend] = {}
        self._db_bootstrapper = DatabaseBootstrapper()
        self._project_root = Path(__file__).resolve().parents[3]
        logger.info(
            "[Storage] Orchestrator created (project_root=%s)", str(self._project_root)
        )

    async def initialize(self) -> None:
        """Initialize storage backends and ensure database readiness."""
        if self._state.initialized:
            logger.info("[Storage] initialize: already initialized; skipping")
            return

        async with self._init_lock:
            if self._state.initialized:
                logger.info("[Storage] initialize: already initialized (after lock)")
                return

            logger.info("[Storage] Initializing Storage orchestrator...")
            logger.info("[Storage] Step 1/4: Ensuring database readiness")
            await self._db_bootstrapper.ensure_database_ready()

            logger.info("[Storage] Step 2/4: Loading storage configs")
            configs = self._load_storage_configs()
            if not configs:
                raise StorageInitializationError("No storage configurations available")
            logger.info("[Storage] Loaded %d storage config(s)", len(configs))

            logger.info("[Storage] Step 3/4: Initializing backends")
            for config in configs:
                logger.info(
                    "[Storage] Preparing backend id=%s provider=%s active=%s",
                    config.id,
                    getattr(config.connection.provider, "value", "unknown"),
                    getattr(config, "is_active", False),
                )
                backend = self._create_backend(config)
                try:
                    logger.info("[Storage] -> initializing backend '%s'", config.id)
                    await backend.initialize()
                    logger.info("[Storage] -> backend '%s' initialized OK", config.id)
                except Exception as exc:
                    logger.error(
                        "Failed to initialize storage backend %s (%s): %s",
                        config.id,
                        config.connection.provider.value,
                        exc,
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
            logger.info(
                "[Storage] Step 4/4: Initialization complete. Default backend='%s' (available=%d)",
                self._state.default_backend_id,
                len(self._backends),
            )

    async def get_backend(self, backend_id: str) -> BaseStorageBackend:
        logger.info("[Storage] get_backend(%s)", backend_id)
        await self.initialize()
        backend = self._backends.get(backend_id)
        if backend is None:
            raise StorageError(f"Storage backend not found: {backend_id}")
        return backend

    async def get_default_backend(self) -> BaseStorageBackend:
        logger.info("[Storage] get_default_backend()")
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
        logger.info("[Storage] _load_storage_configs: begin")

        # Try to load MinIO configuration first (if fully provided)
        try:
            minio_env = read_minio_config()
            if minio_env.get("access_key") and minio_env.get("secret_key"):
                logger.info(
                    "[Storage] MinIO config detected (endpoint=%s, bucket=%s, secure=%s)",
                    minio_env.get("endpoint") or minio_env.get("address"),
                    minio_env.get("bucket_name"),
                    minio_env.get("secure"),
                )
                minio_config = StorageConfig.from_env_config(
                    minio_env, config_id="minio-default"
                )
                configs.append(minio_config)
        except Exception as exc:
            logger.warning("Failed to load MinIO configuration: %s", exc)

        # Always include a local fallback storage
        local_base_path = os.getenv(
            "UNIFILES_STORAGE_LOCAL_BASE_PATH",
            str(self._project_root / "storage_data"),
        )
        try:
            logger.info(
                "[Storage] Adding local storage fallback (base_path=%s)",
                local_base_path,
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
            logger.error("Failed to prepare local storage configuration: %s", exc)

        logger.info("[Storage] _load_storage_configs: done (count=%d)", len(configs))
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


# Global storage singleton -----------------------------------------------------

_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """Return the global storage orchestrator instance (without initializing)."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance


async def get_initialized_storage() -> Storage:
    """Return the storage orchestrator ensuring initialization has run."""
    logger.info("[Storage] get_initialized_storage(): ensure initialized")
    storage = get_storage()
    await storage.initialize()
    return storage
