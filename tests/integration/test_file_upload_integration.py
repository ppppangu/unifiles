"""
Integration tests for file upload functionality in unifiles.app.routers.unifiles

Tests the complete file upload workflow including:
- Authentication middleware
- File validation
- Upload, list, get, update, delete operations
- Public access endpoints
- Error handling and edge cases
"""

import io
import time
from typing import Dict, Optional

import pytest
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder


class TestFileUploadIntegration:
    """Integration tests for file upload endpoints"""

    BASE_URL = "http://127.0.0.1:8088"

    # Test user credentials (should match your auth system)
    TEST_USER = {
        "user_id": "test_user_123",
        "auth_token": "Bearer valid_test_token"
    }

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - ensure service is running"""
        time.sleep(0.5)

        try:
            response = requests.get(f"{self.BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Service not running or not healthy")
        except requests.exceptions.RequestException:
            pytest.skip("Service not accessible")

    @pytest.fixture
    def auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests"""
        return {
            "Authorization": self.TEST_USER["auth_token"],
            "Content-Type": "application/json"
        }

    @pytest.fixture
    def sample_text_file(self) -> io.BytesIO:
        """Create a sample text file for testing"""
        content = "This is a test file for upload integration testing.\nLine 2 of content."
        return io.BytesIO(content.encode('utf-8'))

    @pytest.fixture
    def sample_pdf_content(self) -> io.BytesIO:
        """Create a minimal PDF content for testing"""
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n177\n%%EOF"
        return io.BytesIO(pdf_content)

    def test_get_supported_file_types(self):
        """Test GET /files/types endpoint"""
        response = requests.get(f"{self.BASE_URL}/files/types")

        assert response.status_code == 200
        data = response.json()

        assert "document_types" in data
        assert "pdf_types" in data
        assert "code_types" in data
        assert "all_types" in data

        assert ".txt" in data["document_types"]
        assert ".pdf" in data["pdf_types"]
        assert ".py" in data["code_types"]
        assert ".txt" in data["all_types"]

class TestFileUploadAuth:
    """Test file upload with authentication"""

    BASE_URL = "http://127.0.0.1:8088"

    def test_upload_file_without_auth(self):
        """Test that file upload requires authentication"""
        files = {'file': ('test.txt', 'content', 'text/plain')}

        response = requests.post(f"{self.BASE_URL}/files", files=files)

        # Should return 401 Unauthorized or similar
        assert response.status_code in [401, 403]

    def test_upload_file_with_invalid_auth(self):
        """Test file upload with invalid authentication"""
        headers = {"Authorization": "Bearer invalid_token"}
        files = {'file': ('test.txt', 'content', 'text/plain')}

        response = requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        assert response.status_code in [401, 403]

    @pytest.mark.skip(reason="Requires valid auth token - enable when auth is configured")
    def test_upload_file_success(self):
        """Test successful file upload with valid authentication"""
        headers = {"Authorization": "Bearer valid_test_token"}

        # Create multipart form data
        multipart_data = MultipartEncoder(
            fields={
                'file': ('test.txt', 'Test file content for upload', 'text/plain'),
                'is_public': 'false'
            }
        )
        headers['Content-Type'] = multipart_data.content_type

        response = requests.post(
            f"{self.BASE_URL}/files",
            data=multipart_data,
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "file" in data
        assert "file_id" in data["file"]
        assert data["file"]["filename"] == "test.txt"
        assert data["file"]["user_id"] == "test_user_123"


class TestFileOperations:
    """Test CRUD operations on files"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.fixture
    def uploaded_file_id(self) -> Optional[str]:
        """Upload a file and return its ID for testing other operations"""
        # This would require valid auth - return None for now
        return None

    @pytest.mark.skip(reason="Requires valid auth and uploaded file")
    def test_list_user_files(self, uploaded_file_id):
        """Test GET /files endpoint to list user files"""
        headers = {"Authorization": "Bearer valid_test_token"}

        response = requests.get(
            f"{self.BASE_URL}/files?limit=10&offset=0",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "files" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["files"], list)

    @pytest.mark.skip(reason="Requires valid auth and uploaded file")
    def test_get_file_info(self, uploaded_file_id):
        """Test GET /files/{file_id} endpoint"""
        if not uploaded_file_id:
            pytest.skip("No uploaded file available")

        headers = {"Authorization": "Bearer valid_test_token"}

        response = requests.get(
            f"{self.BASE_URL}/files/{uploaded_file_id}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "file_id" in data
        assert "filename" in data
        assert "user_id" in data
        assert data["file_id"] == uploaded_file_id

    @pytest.mark.skip(reason="Requires valid auth and uploaded file")
    def test_update_file_public_status(self, uploaded_file_id):
        """Test PATCH /files/{file_id}/public-status endpoint"""
        if not uploaded_file_id:
            pytest.skip("No uploaded file available")

        headers = {"Authorization": "Bearer valid_test_token"}

        response = requests.patch(
            f"{self.BASE_URL}/files/{uploaded_file_id}/public-status?is_public=true",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "public status updated" in data["message"].lower()

    @pytest.mark.skip(reason="Requires valid auth and uploaded file")
    def test_delete_file(self, uploaded_file_id):
        """Test DELETE /files/{file_id} endpoint"""
        if not uploaded_file_id:
            pytest.skip("No uploaded file available")

        headers = {"Authorization": "Bearer valid_test_token"}

        response = requests.delete(
            f"{self.BASE_URL}/files/{uploaded_file_id}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "deleted successfully" in data["message"].lower()


class TestPublicAccess:
    """Test public file access endpoints"""

    BASE_URL = "http://127.0.0.1:8088"

    def test_get_public_file_not_found(self):
        """Test GET /files/public/{file_id} with non-existent file"""
        fake_file_id = "non_existent_file_123"

        response = requests.get(f"{self.BASE_URL}/files/public/{fake_file_id}")

        assert response.status_code == 404

    @pytest.mark.skip(reason="Requires a public file to exist")
    def test_get_public_file_success(self):
        """Test successful public file access"""
        # This would need a known public file ID
        public_file_id = "known_public_file_id"

        response = requests.get(f"{self.BASE_URL}/files/public/{public_file_id}")

        assert response.status_code == 200
        data = response.json()

        assert "file_id" in data
        assert "filename" in data
        assert data["is_public"] is True


class TestAdminEndpoints:
    """Test admin endpoints"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.mark.skip(reason="Requires admin authentication")
    def test_get_storage_health(self):
        """Test GET /files/admin/health endpoint"""
        headers = {"Authorization": "Bearer admin_token"}

        response = requests.get(f"{self.BASE_URL}/files/admin/health", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Should contain storage backend health information
        assert isinstance(data, dict)

    @pytest.mark.skip(reason="Requires admin authentication")
    def test_get_storage_metrics(self):
        """Test GET /files/admin/metrics endpoint"""
        headers = {"Authorization": "Bearer admin_token"}

        response = requests.get(f"{self.BASE_URL}/files/admin/metrics", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, dict)


class TestUserStats:
    """Test user statistics endpoints"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.mark.skip(reason="Requires valid user authentication")
    def test_get_user_storage_stats(self):
        """Test GET /files/user/stats endpoint"""
        headers = {"Authorization": "Bearer valid_test_token"}

        response = requests.get(f"{self.BASE_URL}/files/user/stats", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], dict)


class TestFileValidation:
    """Test file validation scenarios"""

    BASE_URL = "http://127.0.0.1:8088"

    def test_upload_empty_file(self):
        """Test uploading an empty file"""
        headers = {"Authorization": "Bearer valid_test_token"}
        files = {'file': ('empty.txt', '', 'text/plain')}

        response = requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        # Should handle empty files gracefully
        assert response.status_code in [400, 422]  # Bad request or validation error

    def test_upload_no_filename(self):
        """Test uploading file without filename"""
        headers = {"Authorization": "Bearer valid_test_token"}
        files = {'file': ('', 'content', 'text/plain')}

        response = requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        assert response.status_code in [400, 422]

    def test_upload_unsupported_file_type(self):
        """Test uploading unsupported file type"""
        headers = {"Authorization": "Bearer valid_test_token"}
        files = {'file': ('virus.exe', b'fake executable content', 'application/x-executable')}

        response = requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        # Should reject unsupported file types
        assert response.status_code in [400, 422]

    def test_upload_large_file(self):
        """Test uploading a large file (size limit check)"""
        headers = {"Authorization": "Bearer valid_test_token"}

        # Create a large file content (e.g., 10MB)
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        files = {'file': ('large.txt', large_content, 'text/plain')}

        response = requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        # Response depends on configured file size limits
        # Could be 200 (success) or 413 (payload too large)
        assert response.status_code in [200, 413, 422]


class TestErrorHandling:
    """Test error scenarios and edge cases"""

    BASE_URL = "http://127.0.0.1:8088"

    def test_get_file_not_found(self):
        """Test getting non-existent file"""
        headers = {"Authorization": "Bearer valid_test_token"}
        fake_file_id = "non_existent_file_123"

        response = requests.get(
            f"{self.BASE_URL}/files/{fake_file_id}",
            headers=headers
        )

        assert response.status_code == 404

    def test_delete_file_not_found(self):
        """Test deleting non-existent file"""
        headers = {"Authorization": "Bearer valid_test_token"}
        fake_file_id = "non_existent_file_123"

        response = requests.delete(
            f"{self.BASE_URL}/files/{fake_file_id}",
            headers=headers
        )

        assert response.status_code == 404

    def test_access_other_user_file(self):
        """Test accessing file owned by another user"""
        headers = {"Authorization": "Bearer valid_test_token"}
        other_user_file_id = "other_user_file_123"

        response = requests.get(
            f"{self.BASE_URL}/files/{other_user_file_id}",
            headers=headers
        )

        # Should return 403 Forbidden or 404 Not Found
        assert response.status_code in [403, 404]

    def test_invalid_file_id_format(self):
        """Test requests with malformed file IDs"""
        headers = {"Authorization": "Bearer valid_test_token"}
        invalid_file_id = "../../../etc/passwd"

        response = requests.get(
            f"{self.BASE_URL}/files/{invalid_file_id}",
            headers=headers
        )

        # Should handle malformed IDs safely
        assert response.status_code in [400, 404, 422]


class TestConcurrency:
    """Test concurrent operations"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.mark.skip(reason="Requires valid auth and multiple test files")
    def test_concurrent_uploads(self):
        """Test multiple simultaneous file uploads"""
        import concurrent.futures

        headers = {"Authorization": "Bearer valid_test_token"}

        def upload_file(file_num):
            files = {'file': (f'test_{file_num}.txt', f'Content {file_num}', 'text/plain')}
            return requests.post(f"{self.BASE_URL}/files", files=files, headers=headers)

        # Upload 5 files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All uploads should succeed
        for response in results:
            assert response.status_code == 200


class TestPagination:
    """Test pagination in file listing"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.mark.skip(reason="Requires valid auth and multiple test files")
    def test_file_list_pagination(self):
        """Test file listing with pagination parameters"""
        headers = {"Authorization": "Bearer valid_test_token"}

        # Test first page
        response = requests.get(
            f"{self.BASE_URL}/files?limit=5&offset=0",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 5
        assert data["offset"] == 0
        assert len(data["files"]) <= 5

        # Test second page if there are more files
        if data["total"] > 5:
            response = requests.get(
                f"{self.BASE_URL}/files?limit=5&offset=5",
                headers=headers
            )

            assert response.status_code == 200
            data2 = response.json()

            assert data2["limit"] == 5
            assert data2["offset"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
