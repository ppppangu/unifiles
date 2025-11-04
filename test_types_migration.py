"""
测试类型系统迁移

验证新的 FastAPI 风格类型系统是否正常工作
"""

def test_top_level_imports():
    """测试顶层导入（80%场景）"""
    from unifiles.types import (
        # Users
        UserModel,
        AccessKeyModel,
        # Files
        FileModel,
        FileStatus,
        FileProcessingLogModel,
        # Storage
        ProviderType,
        ConfigSource,
        StorageConfig,
        MinIOConnection,
        S3Connection,
        ConnectionConfig,
        create_connection_from_dict,
        # Processing
        ProcessingStatus,
        ProcessingStage,
        # Knowledge Base
        KnowledgeBaseModel,
        DocumentModel,
        KnowledgeBaseStatus,
        # Extraction
        ExtractedDocumentModel,
        ExtractionStatus,
    )
    print("[OK] Top-level imports (80% use case)")


def test_core_module_imports():
    """测试核心模块导入（15%场景）"""
    from unifiles.types.core import (
        # All types
        UserModel,
        FileModel,
        ChunkModel,
        PhotoModel,
        ComponentModel,
        ExtractedAssetModel,
        KBStatisticsModel,
    )
    print("[OK] Core module imports (15% use case)")


def test_specific_imports():
    """测试特定导入（5%场景）"""
    from unifiles.types.core.extraction import ExtractedAssetModel
    from unifiles.types.core.components import ChunkModel, PhotoModel
    from unifiles.types.core.storage import AzureConnection, GCSConnection
    print("[OK] Specific imports (5% use case)")


def test_backward_compatibility():
    """测试向后兼容性"""
    from unifiles.core.config.models import StorageConfig, ProviderType
    from unifiles.core.database import FileModel, UserModel, FileStatus
    print("[OK] Backward compatibility imports")


def test_instance_creation():
    """测试实例创建"""
    from unifiles.types import (
        FileModel,
        FileStatus,
        UserModel,
        MinIOConnection,
        ProviderType,
    )

    # Create a user
    user = UserModel(id="user-123", username="test_user")
    assert user.id == "user-123"

    # Create a file
    file = FileModel(
        id="file-123",
        user_id="user-123",
        filename="test.pdf",
        status=FileStatus.UPLOADED,
    )
    assert file.status == FileStatus.UPLOADED

    # Create a MinIO connection
    conn = MinIOConnection(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="test-bucket",
    )
    assert conn.provider == ProviderType.MINIO

    print("[OK] Instance creation works")


def test_enum_values():
    """测试枚举值"""
    from unifiles.types import FileStatus, ProviderType, ProcessingStatus
    from unifiles.types.core import ComponentType, ExtractionStatus

    assert FileStatus.UPLOADED.value == "uploaded"
    assert ProviderType.MINIO.value == "minio"
    assert ProcessingStatus.COMPLETED.value == "completed"
    assert ComponentType.CHUNK.value == "chunk"
    assert ExtractionStatus.COMPLETED.value == "completed"

    print("[OK] Enum values correct")


if __name__ == "__main__":
    print("Testing types migration...")
    print()

    test_top_level_imports()
    test_core_module_imports()
    test_specific_imports()
    test_backward_compatibility()
    test_instance_creation()
    test_enum_values()

    print()
    print("=" * 50)
    print("All tests passed!")
    print("Types migration successful!")
    print("=" * 50)
