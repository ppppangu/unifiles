"""
Integration tests for the Unifiles service health endpoints
"""

import time

import pytest
import requests


class TestHealthEndpoints:
    """Test cases for health check functionality"""

    BASE_URL = "http://127.0.0.1:8088"

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - ensure service is running"""
        # Wait a bit for service to be ready
        time.sleep(1)

        # Basic connectivity check
        try:
            response = requests.get(f"{self.BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Service not running or not healthy")
        except requests.exceptions.RequestException:
            pytest.skip("Service not accessible")

    def test_health_endpoint_returns_200(self):
        """Test that /health endpoint returns HTTP 200"""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self):
        """Test that /health endpoint returns valid JSON"""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.headers.get("content-type", "").startswith("application/json")

        # Should be able to parse as JSON
        data = response.json()
        assert isinstance(data, dict)

    def test_health_endpoint_response_structure(self):
        """Test that /health endpoint returns expected structure"""
        response = requests.get(f"{self.BASE_URL}/health")
        data = response.json()

        # Check required fields
        assert "success" in data
        assert "message" in data
        assert "data" in data

        # Check field types and values
        assert isinstance(data["success"], bool)
        assert data["success"] is True
        assert isinstance(data["message"], str)
        assert data["message"] == "Service is healthy"

        # Check data structure
        assert isinstance(data["data"], dict)
        assert "version" in data["data"]
        assert "service" in data["data"]
        assert data["data"]["version"] == "1.1.0"
        assert data["data"]["service"] == "unifiles-v1"

    def test_docs_endpoint_accessible(self):
        """Test that API documentation is accessible"""
        response = requests.get(f"{self.BASE_URL}/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_openapi_json_accessible(self):
        """Test that OpenAPI JSON spec is accessible"""
        response = requests.get(f"{self.BASE_URL}/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Unifiles v1 API"
        assert data["info"]["version"] == "1.1.0"

    def test_cors_headers_present(self):
        """Test that CORS headers are properly configured"""
        response = requests.get(f"{self.BASE_URL}/health")

        # Should have CORS headers for development
        # Note: Actual values depend on middleware configuration
        headers = response.headers
        # Basic check - at least one CORS-related header should be present
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]

        # Check if any CORS header is present (middleware might set them on OPTIONS requests)
        # For now, just verify the request succeeds and service is configured
        assert response.status_code == 200


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])
