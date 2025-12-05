# Changelog

All notable changes to the Unifiles Python Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-12-05

### Security Fixes 🔒

- **[CRITICAL]** Fixed authentication bypass vulnerability in `/users/*` endpoints
  - Removed overly broad `/users/` prefix from public path list in middleware
  - All `/users/*` endpoints now require authentication except `/users/create`
  - Prevents unauthorized access to sensitive operations like access key management
  - **File**: `unifiles/app/middlewares.py:261-266`

- **[HIGH]** Added admin role validation for protected endpoints
  - `/files/admin/health` now requires admin role
  - `/files/admin/metrics` now requires admin role
  - `/manager/system/status` now requires authentication and admin role
  - Returns HTTP 403 Forbidden when non-admin users attempt access
  - **Files**:
    - `unifiles/app/routers/unifiles.py:280-282, 301-303`
    - `unifiles/app/routers/manager.py:23-30`

### Bug Fixes 🐛

- **[CRITICAL]** Fixed AttributeError crash in `EmbeddingService.get_service_info()`
  - Removed reference to uninitialized `batch_processor.concurrency_limit`
  - Method was causing runtime crash when service info endpoint was called
  - **File**: `unifiles/core/services/embedding_service.py:277-279`

- **[HIGH]** Fixed incorrect HTTP status code in admin endpoint error handling
  - Admin role validation now occurs outside try-except blocks
  - Previously, 403 Forbidden errors were incorrectly converted to 500 Internal Server Error
  - Clients now receive correct status codes: 403 for permission denied, 500 for server errors
  - **Files**: `unifiles/app/routers/unifiles.py:279-281, 300-302`, `unifiles/app/routers/manager.py:27-29`

- **[HIGH]** Fixed bootstrap access key creation for new users
  - New users can now create their first access key without authentication
  - POST requests to `/users/{user_id}/access-keys` are allowed without Bearer token
  - Subsequent access key operations still require authentication
  - Resolves "chicken-and-egg" problem where users couldn't get initial access key
  - **File**: `unifiles/app/middlewares.py:326-330`

### Breaking Changes ⚠️

- **Authentication now required for most `/users/*` endpoints**
  - Previously: All `/users/*` endpoints were publicly accessible
  - Now:
    - **Public** (no auth): `POST /users/create`, `POST /users/{user_id}/access-keys` (for bootstrap)
    - **Protected** (auth required): `GET /users/{user_id}/access-keys`, `DELETE /users/{user_id}/access-keys/{key_id}`, and all other user endpoints
  - **Impact**: API clients listing or deleting access keys must include authentication
  - **Migration**: Add `Authorization: Bearer <access_key>` header for GET/DELETE operations on access keys

### Migration Guide 📋

For API clients using `/users/*` endpoints:

#### New User Registration Flow
1. **Create user** (no auth required):
   ```bash
   curl -X POST "http://localhost:8088/users/create" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123", "username": "john", "email": "john@example.com"}'
   ```

2. **Create first access key** (no auth required for bootstrap):
   ```bash
   curl -X POST "http://localhost:8088/users/user123/access-keys" \
     -H "Content-Type: application/json" \
     -d '{"description": "My first key"}'
   ```

3. **Use access key for subsequent operations** (auth required):
   ```bash
   # List access keys (requires auth)
   curl -X GET "http://localhost:8088/users/user123/access-keys" \
     -H "Authorization: Bearer [REDACTED]"

   # Delete access key (requires auth)
   curl -X DELETE "http://localhost:8088/users/user123/access-keys/key_abc123" \
     -H "Authorization: Bearer [REDACTED]"
   ```

#### Public Endpoints (No Authentication Required)
- `POST /users/create` - Create new user
- `POST /users/{user_id}/access-keys` - Create access key (intended for bootstrap)

#### Protected Endpoints (Authentication Required)
- `GET /users/{user_id}/access-keys` - List access keys
- `DELETE /users/{user_id}/access-keys/{key_id}` - Delete access key
- All other `/users/*` endpoints

### Files Modified 📝

- `unifiles/app/middlewares.py` - Authentication middleware security fix
- `unifiles/core/services/embedding_service.py` - AttributeError crash fix
- `unifiles/app/routers/unifiles.py` - Admin role validation (2 endpoints)
- `unifiles/app/routers/manager.py` - Admin role validation and authentication

---

## [1.0.0] - 2024-01-XX

### Added
- 🎉 Initial release of Unifiles Python Client
- 📁 **File Storage Layer** - Upload and manage original files
  - File upload with validation and error handling
  - Support for multiple file types (PDF, DOC, images, etc.)
  - File size and type validation
  - Public/private file access control
- 🔍 **Content Extraction Layer** - OCR processing and content extraction
  - Automatic content extraction from uploaded files
  - Support for both text and image content types
  - OCR processing for scanned documents and images
  - Markdown content generation
  - Extraction metadata and processing status
- 📚 **Knowledge Base Layer** - Document indexing and management
  - Knowledge base creation and management
  - Document chunking strategies (semantic, fixed, sliding)
  - Vector indexing for search and retrieval
  - Knowledge base document listing and management
- 🚀 **One-Click Processing** - Simplified workflow automation
  - `quick_process()` method for end-to-end document processing
  - Automatic progression through all three layers
  - Smart knowledge base creation and management
- 🛡️ **Comprehensive Error Handling**
  - Custom exception hierarchy for different error types
  - HTTP status code handling and retry logic
  - Network connection error management
  - API business logic error handling
- 🔧 **Developer Experience**
  - Full type hints for better IDE support
  - Comprehensive documentation and examples
  - Pythonic API design following best practices
  - Detailed error messages and debugging information
- 📖 **Documentation and Examples**
  - Complete API documentation
  - Usage examples for all major features
  - Quick start guide and tutorials
  - Best practices and advanced usage patterns

### Technical Features
- **Client Architecture**
  - `Unifile` - Main client entry point
  - `Document` - Document lifecycle management
  - `KnowledgeBase` - Knowledge base operations
  - Enum types for status and content types
- **Error Management**
  - `UnifilesError` - Base exception class
  - `DocumentNotFoundError` - Document-specific errors
  - `KnowledgeBaseNotFoundError` - Knowledge base errors
  - `AuthenticationError` - Authentication failures
  - `RateLimitError` - Rate limiting errors
- **File Support**
  - Documents: PDF, DOC, DOCX, TXT, MD
  - Images: JPG, JPEG, PNG, TIFF
  - Maximum file size: 100MB
  - Automatic MIME type detection
- **Processing Features**
  - Multiple extraction modes (simple, normal)
  - Content type separation (text vs image)
  - Processing status tracking
  - Timeout and polling configuration

### Dependencies
- `requests>=2.28.0` - HTTP client library
- `pathlib2>=2.3.0` - Path handling (Python <3.6)
- Python 3.8+ support

### Development Tools
- Full test suite with pytest
- Code formatting with Black
- Import sorting with isort
- Type checking with mypy
- Pre-commit hooks for code quality

## [Unreleased]

### Planned Features
- 🔄 Async client support with `aiohttp`
- 📊 Progress tracking and callback support
- 🔍 Advanced search and filtering capabilities
- 📈 Batch processing utilities
- 🔧 Configuration file support
- 📱 CLI tool for command-line usage
- 🐳 Docker container examples
- 📝 Additional content extraction formats
- 🔐 Enhanced authentication methods
- ⚡ Performance optimization and caching

---

## Legend
- 🎉 Major features
- 📁 File storage
- 🔍 Content extraction  
- 📚 Knowledge base
- 🚀 Automation
- 🛡️ Security/Error handling
- 🔧 Developer experience
- 📖 Documentation
- 🔄 Async features
- 📊 Analytics/tracking
- 📈 Performance
- 🔐 Security
- 📝 Content formats
- 📱 CLI/Tools
- 🐳 Deployment