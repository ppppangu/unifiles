"""
Connection configuration models for storage providers
Provides type-safe, provider-specific connection configurations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union


class ProviderType(str, Enum):
    """Storage provider types"""

    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"


@dataclass
class BaseConnection(ABC):
    """Base class for all storage connection configurations"""

    provider: ProviderType

    @abstractmethod
    def validate_connection(self) -> None:
        """Validate provider-specific connection parameters"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert connection to dictionary representation"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseConnection":
        """Create connection instance from dictionary"""
        pass


@dataclass
class LocalConnection(BaseConnection):
    """Local filesystem storage connection"""

    provider: Literal[ProviderType.LOCAL] = ProviderType.LOCAL
    base_path: str = field(default="")
    create_if_missing: bool = field(default=True)

    def validate_connection(self) -> None:
        """Validate local connection parameters"""
        if not self.base_path:
            raise ValueError("Local storage requires base_path")

        # Ensure path is absolute for security
        from pathlib import Path

        path = Path(self.base_path)
        if not path.is_absolute():
            raise ValueError("Local storage base_path must be absolute")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "provider": self.provider.value,
            "base_path": self.base_path,
            "create_if_missing": self.create_if_missing,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalConnection":
        """Create from dictionary"""
        return cls(
            base_path=data.get("base_path", ""),
            create_if_missing=data.get("create_if_missing", True),
        )


@dataclass
class MinIOConnection(BaseConnection):
    """MinIO object storage connection"""

    provider: Literal[ProviderType.MINIO] = ProviderType.MINIO
    endpoint: str = field(default="")
    access_key: str = field(default="")
    secret_key: str = field(default="")
    bucket_name: str = field(default="")
    region: str = field(default="us-east-1")
    secure: bool = field(default=True)

    def validate_connection(self) -> None:
        """Validate MinIO connection parameters"""
        required_fields = ["endpoint", "access_key", "secret_key", "bucket_name"]
        missing_fields = []

        for field_name in required_fields:
            if not getattr(self, field_name):
                missing_fields.append(field_name)

        if missing_fields:
            raise ValueError(
                f"MinIO connection missing required fields: {', '.join(missing_fields)}"
            )

        # Validate endpoint format (remove protocol if present)
        if self.endpoint and "://" in self.endpoint:
            # Extract hostname:port from full URL
            from urllib.parse import urlparse

            parsed = urlparse(self.endpoint)
            if parsed.netloc:
                self.endpoint = parsed.netloc

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket_name": self.bucket_name,
            "region": self.region,
            "secure": self.secure,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MinIOConnection":
        """Create from dictionary"""
        return cls(
            endpoint=data.get("endpoint", ""),
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket_name=data.get("bucket_name", ""),
            region=data.get("region", "us-east-1"),
            secure=data.get("secure", True),
        )


@dataclass
class S3Connection(BaseConnection):
    """AWS S3 storage connection"""

    provider: Literal[ProviderType.S3] = ProviderType.S3
    access_key: str = field(default="")
    secret_key: str = field(default="")
    bucket_name: str = field(default="")
    region: str = field(default="us-east-1")
    endpoint: Optional[str] = field(default=None)  # For S3-compatible services

    def validate_connection(self) -> None:
        """Validate S3 connection parameters"""
        required_fields = ["access_key", "secret_key", "bucket_name", "region"]
        missing_fields = []

        for field_name in required_fields:
            if not getattr(self, field_name):
                missing_fields.append(field_name)

        if missing_fields:
            raise ValueError(
                f"S3 connection missing required fields: {', '.join(missing_fields)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "provider": self.provider.value,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket_name": self.bucket_name,
            "region": self.region,
        }
        if self.endpoint:
            result["endpoint"] = self.endpoint
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "S3Connection":
        """Create from dictionary"""
        return cls(
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket_name=data.get("bucket_name", ""),
            region=data.get("region", "us-east-1"),
            endpoint=data.get("endpoint"),
        )


@dataclass
class AzureConnection(BaseConnection):
    """Azure Blob Storage connection"""

    provider: Literal[ProviderType.AZURE] = ProviderType.AZURE
    account_name: str = field(default="")
    container_name: str = field(default="")
    # Either account_key or sas_token should be provided
    account_key: Optional[str] = field(default=None)
    sas_token: Optional[str] = field(default=None)

    def validate_connection(self) -> None:
        """Validate Azure connection parameters"""
        if not self.account_name:
            raise ValueError("Azure connection requires account_name")

        if not self.container_name:
            raise ValueError("Azure connection requires container_name")

        if not self.account_key and not self.sas_token:
            raise ValueError(
                "Azure connection requires either account_key or sas_token"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "provider": self.provider.value,
            "account_name": self.account_name,
            "container_name": self.container_name,
        }
        if self.account_key:
            result["account_key"] = self.account_key
        if self.sas_token:
            result["sas_token"] = self.sas_token
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AzureConnection":
        """Create from dictionary"""
        return cls(
            account_name=data.get("account_name", ""),
            container_name=data.get("container_name", ""),
            account_key=data.get("account_key"),
            sas_token=data.get("sas_token"),
        )


@dataclass
class GCSConnection(BaseConnection):
    """Google Cloud Storage connection"""

    provider: Literal[ProviderType.GCS] = ProviderType.GCS
    bucket_name: str = field(default="")
    # Either credentials_json_path or service_account_key_json should be provided
    credentials_json_path: Optional[str] = field(default=None)
    service_account_key_json: Optional[str] = field(default=None)
    project_id: Optional[str] = field(default=None)

    def validate_connection(self) -> None:
        """Validate GCS connection parameters"""
        if not self.bucket_name:
            raise ValueError("GCS connection requires bucket_name")

        if not self.credentials_json_path and not self.service_account_key_json:
            raise ValueError(
                "GCS connection requires either credentials_json_path or service_account_key_json"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {"provider": self.provider.value, "bucket_name": self.bucket_name}
        if self.credentials_json_path:
            result["credentials_json_path"] = self.credentials_json_path
        if self.service_account_key_json:
            result["service_account_key_json"] = self.service_account_key_json
        if self.project_id:
            result["project_id"] = self.project_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GCSConnection":
        """Create from dictionary"""
        return cls(
            bucket_name=data.get("bucket_name", ""),
            credentials_json_path=data.get("credentials_json_path"),
            service_account_key_json=data.get("service_account_key_json"),
            project_id=data.get("project_id"),
        )


# Discriminated union type for all connection types
ConnectionConfig = Union[
    LocalConnection, MinIOConnection, S3Connection, AzureConnection, GCSConnection
]


def create_connection_from_dict(data: Dict[str, Any]) -> ConnectionConfig:
    """
    Factory function to create appropriate connection instance from dictionary

    Args:
        data: Dictionary containing connection configuration

    Returns:
        Appropriate connection instance

    Raises:
        ValueError: If provider type is unsupported or data is invalid
    """
    provider_str = data.get("provider", "").lower()

    # Map string to enum
    try:
        provider = ProviderType(provider_str)
    except ValueError:
        available_providers = ", ".join([p.value for p in ProviderType])
        raise ValueError(
            f"Unsupported provider: '{provider_str}'. Available: {available_providers}"
        )

    # Create appropriate connection instance
    connection_classes = {
        ProviderType.LOCAL: LocalConnection,
        ProviderType.MINIO: MinIOConnection,
        ProviderType.S3: S3Connection,
        ProviderType.AZURE: AzureConnection,
        ProviderType.GCS: GCSConnection,
    }

    connection_class = connection_classes.get(provider)
    if not connection_class:
        raise ValueError(f"No connection class found for provider: {provider}")

    return connection_class.from_dict(data)


# Legacy conversion function removed - this is a first-version system
