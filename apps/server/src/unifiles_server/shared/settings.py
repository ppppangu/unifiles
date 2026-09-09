from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNIFILES_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path(".unifiles-data"))
    bootstrap_api_key: SecretStr | None = Field(default=None, repr=False)
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    max_file_size_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    storage_limit_bytes: int = Field(default=10 * 1024 * 1024 * 1024, gt=0)
    extraction_pages_limit: int = Field(default=100_000, gt=0)
    knowledge_base_limit: int = Field(default=1_000, gt=0)
    ocr_endpoint: str | None = None
    ocr_api_key: SecretStr | None = Field(default=None, repr=False)
    ocr_timeout_seconds: float = Field(default=120, gt=0)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "unifiles.sqlite3"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


settings = Settings()
