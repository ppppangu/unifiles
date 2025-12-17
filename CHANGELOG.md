# Changelog

All notable changes to the Unifiles Python Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-12-17

### Added ✨

- **PDF Conversion Support** - Comprehensive client-side handling for async PDF conversion tasks
  - Added `Document.conversion_status` property - Returns conversion status (pending/processing/completed/failed/skipped)
  - Added `Document.is_converted` property - Boolean flag indicating if file was converted to PDF
  - Added `Document.derived_pdf_url` property - URL of the converted PDF file
  - Added `Document.wait_for_conversion(timeout, poll_interval)` method - Wait for PDF conversion to complete
  - **Files**: `unifiles_client/client.py:230-273, 383-455`

- **Auto-Wait Conversion in Upload** - `upload_file()` now waits for PDF conversion by default
  - New parameter: `wait_for_conversion: bool = True` - Control auto-wait behavior
  - New parameter: `conversion_timeout: int = 300` - Maximum time to wait for conversion
  - Automatically blocks until .docx/.pptx conversion completes
  - PDF files and non-convertible files return immediately (no waiting)
  - Emits warning if conversion fails but upload succeeds
  - **File**: `unifiles_client/client.py:848-972`

- **Smart Extraction Pre-Check** - `extract_content()` automatically waits for pending conversions
  - Checks conversion status before triggering extraction
  - Waits for pending/processing conversions to complete
  - Ensures OCR uses converted PDF for optimal quality
  - Emits warning if conversion incomplete but allows extraction on original file
  - **File**: `unifiles_client/client.py:495-515`

### Changed 🔄

- **Upload Behavior for Office Documents** - `.docx`, `.pptx`, `.xlsx` files now auto-wait for conversion by default
  - **Previous**: `upload_file("report.docx")` returned immediately, conversion ran async
  - **Current**: `upload_file("report.docx")` blocks until PDF conversion completes
  - **Opt-Out**: Use `wait_for_conversion=False` for old async behavior
  - **Impact**: Upload operations for Office documents may take longer (typically 5-30 seconds)

- **Document Class Initialization** - Now tracks conversion task ID from server response
  - `Document.__init__` extracts `conversion_task_id` from `file_info` if provided
  - Enables manual conversion waiting via `wait_for_conversion()`
  - **File**: `unifiles_client/client.py:181-186`

### Breaking Changes ⚠️

- **upload_file() Auto-Wait Behavior**
  - **Affected File Types**: `.docx`, `.pptx`, `.xlsx`, and other Office formats
  - **Not Affected**: `.pdf` files (conversion skipped), `.txt`, `.jpg`, etc. (no conversion)
  - **Previous Behavior**:
    ```python
    doc = client.upload_file("report.docx")  # Returned immediately
    # Conversion ran in background
    ```
  - **New Behavior**:
    ```python
    doc = client.upload_file("report.docx")  # Blocks until conversion completes
    print(doc.conversion_status)  # "completed"
    print(doc.derived_pdf_url)    # URL to converted PDF
    ```
  - **Migration Path**: Use `wait_for_conversion=False` for async uploads
    ```python
    doc = client.upload_file("report.docx", wait_for_conversion=False)  # Async
    # Do other work...
    doc.wait_for_conversion()  # Wait manually when needed
    ```

### Migration Guide 📋

#### For Users Uploading Office Documents

**Scenario 1: You want auto-wait behavior (RECOMMENDED)**
```python
# No changes needed - this is now the default
doc = client.upload_file("report.docx")
# Conversion completes automatically
doc.extract_content(mode="mistral")
```

**Scenario 2: You need async upload behavior**
```python
# Opt out of auto-wait
doc = client.upload_file("report.docx", wait_for_conversion=False)

# Upload returns immediately
print(f"Uploaded: {doc.file_id}")

# Wait manually when needed
if doc.wait_for_conversion(timeout=300):
    print("Conversion complete!")
```

**Scenario 3: Checking conversion status**
```python
doc = client.upload_file("presentation.pptx")

# Check conversion status
if doc.is_converted:
    print(f"PDF available: {doc.derived_pdf_url}")
else:
    print(f"Status: {doc.conversion_status}")
```

#### For Users Uploading PDF Files

**No changes required** - PDF files skip conversion entirely:
```python
doc = client.upload_file("already.pdf")
# Returns immediately (no conversion)
print(doc.conversion_status)  # "skipped"
```

### Testing 🧪

- Added comprehensive unit tests in `tests/unit/test_client_conversion.py`
  - 13 test cases covering all conversion scenarios
  - Mock-based tests for properties, waiting, upload, and extraction
  - Tests for success, failure, timeout, and edge cases

- Added integration tests in `tests/test_conversion_integration.py`
  - End-to-end tests with live server
  - Tests for .docx conversion, .pdf upload, extraction flow
  - Requires API server running at http://127.0.0.1:8088

### Documentation 📚

- Updated `README.md` with comprehensive PDF conversion section
  - Auto-wait behavior examples
  - Async upload patterns
  - Conversion status checking
  - Smart extraction pre-check
  - Migration examples

### Developer Notes 🔧

- Server API compatibility: Requires server API v1.1.0+ with conversion endpoints
- Task polling uses existing `/tasks/{task_id}` endpoint
- Conversion status values: `pending`, `processing`, `completed`, `failed`, `skipped`
- Auto-wait uses same timeout/polling pattern as `wait_for_extraction()`
- All changes maintain 100% backward compatibility for PDF files and non-convertible formats

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