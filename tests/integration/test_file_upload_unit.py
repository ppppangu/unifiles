"""
Unit-style integration tests for file upload router logic

These tests mock the dependencies and test the router logic without requiring
a running server or database connections.
"""

import io
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile

from unifiles.server.routers.unifiles import (
    SUPPORTED_FILE_TYPES,
    get_auth_service,
    get_file_service,
)


@pytest.fixture
def mock_user_context():
    """Mock user context from authentication"""
    return {
        "user_id": "test_user_123",
        "client_ip": "127.0.0.1",
        "user_agent": "TestClient/1.0"
    }


@pytest.fixture
def mock_auth_service():
    """Mock authentication service"""
    service = AsyncMock()
    service.extract_user_from_request.return_value = {
        "user_id": "test_user_123",
        "client_ip": "127.0.0.1",
        "user_agent": "TestClient/1.0"
    }
    return service


@pytest.fixture
def mock_file_service():
    """Mock file service"""
    service = AsyncMock()
    service.upload_file.return_value = Mock(
        file=Mock(
            file_id="test_file_123",
            filename="test.txt",
            user_id="test_user_123"
        )
    )
    service.get_user_files.return_value = Mock(
        files=[
            Mock(file_id="test_file_123", filename="test.txt", user_id="test_user_123")
        ]
    )
    service.get_file_info.return_value = Mock(
        file_id="test_file_123",
        filename="test.txt",
        user_id="test_user_123"
    )
    service.delete_file.return_value = {"success": True}
    service.update_file_public_status.return_value = {"success": True}
    service.get_public_file_info.return_value = Mock(
        file_id="public_file_123",
        filename="public.txt",
        is_public=True
    )
    service.get_storage_health.return_value = {"status": "healthy"}
    service.get_storage_metrics.return_value = {"files_count": 100}

    return service


@pytest.fixture
def test_upload_file():
    """Create a test UploadFile object"""
    content = b"Test file content"
    file_obj = io.BytesIO(content)
    upload_file = UploadFile(filename="test.txt", file=file_obj)
    # Mock the content_type property since it's read-only
    upload_file._content_type = "text/plain"
    return upload_file


class TestFileUploadRouter:
    """Test the file upload router endpoints"""

    @pytest.mark.asyncio
    async def test_get_supported_file_types(self):
        """Test the supported file types endpoint"""
        from unifiles.server.routers.unifiles import get_supported_file_types

        # Call the endpoint function directly
        result = await get_supported_file_types()

        assert hasattr(result, 'document_types')
        assert hasattr(result, 'pdf_types')
        assert hasattr(result, 'code_types')
        assert hasattr(result, 'all_types')

        assert ".txt" in result.document_types
        assert ".pdf" in result.pdf_types
        assert ".py" in result.code_types
        assert len(result.all_types) == len(SUPPORTED_FILE_TYPES)

    @pytest.mark.asyncio
    async def test_upload_file_success(
        self, mock_user_context, mock_file_service, test_upload_file
    ):
        """Test successful file upload"""
        from unifiles.server.routers.unifiles import upload_file

        result = await upload_file(
            file=test_upload_file,
            is_public=False,
            user_context=mock_user_context,
            file_service=mock_file_service
        )

        # Verify the file service was called correctly
        mock_file_service.upload_file.assert_called_once()
        call_args = mock_file_service.upload_file.call_args

        assert call_args.kwargs["user_id"] == "test_user_123"
        assert call_args.kwargs["file"] == test_upload_file
        assert call_args.kwargs["is_public"] is False
        assert "client_ip" in call_args.kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_list_user_files(self, mock_user_context, mock_file_service):
        """Test listing user files"""
        from unifiles.server.routers.unifiles import list_user_files

        result = await list_user_files(
            limit=50,
            offset=0,
            user_context=mock_user_context,
            file_service=mock_file_service
        )

        mock_file_service.get_user_files.assert_called_once_with(
            user_id="test_user_123",
            limit=50,
            offset=0
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_file_info(self, mock_user_context, mock_file_service):
        """Test getting file information"""
        from unifiles.server.routers.unifiles import get_file_info

        result = await get_file_info(
            file_id="test_file_123",
            user_context=mock_user_context,
            file_service=mock_file_service
        )

        mock_file_service.get_file_info.assert_called_once_with(
            user_id="test_user_123",
            file_id="test_file_123"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_file_public_status(self, mock_user_context, mock_file_service):
        """Test updating file public status"""
        from unifiles.server.routers.unifiles import update_file_public_status

        result = await update_file_public_status(
            file_id="test_file_123",
            is_public=True,
            user_context=mock_user_context,
            file_service=mock_file_service
        )

        mock_file_service.update_file_public_status.assert_called_once_with(
            user_id="test_user_123",
            file_id="test_file_123",
            is_public=True
        )
        assert result.success is True
        assert "public status updated" in result.message.lower()

    @pytest.mark.asyncio
    async def test_delete_file(self, mock_user_context, mock_file_service):
        """Test file deletion"""
        from unifiles.server.routers.unifiles import delete_file

        result = await delete_file(
            file_id="test_file_123",
            user_context=mock_user_context,
            file_service=mock_file_service
        )

        mock_file_service.delete_file.assert_called_once_with(
            user_id="test_user_123",
            file_id="test_file_123"
        )
        assert result.success is True
        assert "deleted successfully" in result.message.lower()

    @pytest.mark.asyncio
    async def test_get_public_file_info(self, mock_file_service):
        """Test getting public file information"""
        from unifiles.server.routers.unifiles import get_public_file_info

        result = await get_public_file_info(
            file_id="public_file_123",
            file_service=mock_file_service
        )

        mock_file_service.get_public_file_info.assert_called_once_with(
            file_id="public_file_123"
        )
        assert result is not None


class TestErrorHandling:
    """Test error handling in router endpoints"""

    @pytest.mark.asyncio
    async def test_upload_file_service_error(
        self, mock_user_context, test_upload_file
    ):
        """Test upload file when service raises an error"""
        from unifiles.server.routers.unifiles import upload_file

        # Mock file service that raises an exception
        mock_service = AsyncMock()
        mock_service.upload_file.side_effect = Exception("Storage error")

        with pytest.raises(HTTPException) as exc_info:
            await upload_file(
                file=test_upload_file,
                is_public=False,
                user_context=mock_user_context,
                file_service=mock_service
            )

        assert exc_info.value.status_code == 500
        assert "Upload failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_info_service_error(self, mock_user_context):
        """Test get file info when service raises an error"""
        from unifiles.server.routers.unifiles import get_file_info

        mock_service = AsyncMock()
        mock_service.get_file_info.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await get_file_info(
                file_id="test_file_123",
                user_context=mock_user_context,
                file_service=mock_service
            )

        assert exc_info.value.status_code == 500
        assert "Failed to get file info" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_file_service_error(self, mock_user_context):
        """Test delete file when service raises an error"""
        from unifiles.server.routers.unifiles import delete_file

        mock_service = AsyncMock()
        mock_service.delete_file.side_effect = Exception("Storage error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_file(
                file_id="test_file_123",
                user_context=mock_user_context,
                file_service=mock_service
            )

        assert exc_info.value.status_code == 500
        assert "Failed to delete file" in str(exc_info.value.detail)


class TestServiceDependencies:
    """Test dependency injection and service creation"""

    def test_get_file_service(self):
        """Test file service dependency creation"""
        with patch('unifiles.server.routers.unifiles.storage_manager') as mock_storage, \
             patch('unifiles.server.routers.unifiles.secure_file_db_manager') as mock_db:

            mock_storage.return_value = Mock()

            service = get_file_service()

            assert service is not None
            mock_storage.assert_called_once()

    def test_get_auth_service(self):
        """Test auth service dependency creation"""
        with patch('unifiles.core.config.env_config.read_pg_config') as mock_config:
            mock_config.return_value = {"host": "localhost"}

            service = get_auth_service()

            assert service is not None
            mock_config.assert_called_once()


class TestFileConstants:
    """Test file type constants"""

    def test_supported_file_types_coverage(self):
        """Test that all file type constants are properly defined"""
        from unifiles.server.routers.unifiles import (
            CODE_FILE_TYPES,
            DOCUMENT_FILE_TYPES,
            PDF_FILE_TYPES,
            SUPPORTED_FILE_TYPES,
        )

        # Ensure no duplicate types
        all_individual = DOCUMENT_FILE_TYPES + PDF_FILE_TYPES + CODE_FILE_TYPES
        assert len(all_individual) == len(set(all_individual))

        # Ensure SUPPORTED_FILE_TYPES includes all individual types
        assert set(SUPPORTED_FILE_TYPES) == set(all_individual)

        # Test specific file types are present
        assert ".txt" in DOCUMENT_FILE_TYPES
        assert ".pdf" in PDF_FILE_TYPES
        assert ".py" in CODE_FILE_TYPES
        assert ".json" in CODE_FILE_TYPES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
