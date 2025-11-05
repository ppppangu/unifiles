# Unifiles Developer Tutorial

## What You'll Learn

- Understand the three-layer architecture
- Set up a complete development environment
- Write and run tests
- Debug common issues
- Contribute code following best practices

## Prerequisites

- Completed the [Quick Start Guide](../../quickstart.md)
- Python 3.8+ with pip
- Git installed
- Basic knowledge of FastAPI and async Python

## Time Estimate

- Environment setup: 10 minutes
- Architecture walkthrough: 15 minutes
- Testing setup: 10 minutes
- First contribution: 20 minutes

---

## Part 1: Development Environment Setup

### 1.1 Clone and Setup

```bash
# Clone with full history
git clone https://github.com/unifiles/unifiles.git
cd unifiles

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/Mac:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### 1.2 Install Pre-commit Hooks

```bash
# Install pre-commit framework
pip install pre-commit

# Install git hooks
pre-commit install

# Run hooks on all files (first time)
pre-commit run --all-files
```

Expected output:
```
black....................................................................Passed
isort....................................................................Passed
flake8...................................................................Passed
mypy.....................................................................Passed
```

### 1.3 Configure IDE

#### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests"
  ]
}
```

#### PyCharm Settings

1. Go to Settings → Project → Python Interpreter
2. Select the `.venv` interpreter
3. Enable: Editor → Code Style → Python → Use Black formatter
4. Configure: Run → Edit Configurations → Add pytest

---

## Part 2: Understanding the Architecture

### 2.1 Three-Layer Architecture Deep Dive

```python
# architecture_demo.py
"""
Demonstrates the three-layer architecture with actual code
"""

import asyncio
from unifiles.core import FileStorage, ContentExtractor, KnowledgeBase

async def demonstrate_architecture():
    # Layer 1: File Storage
    print("=== Layer 1: File Storage ===")
    storage = FileStorage()
    
    # Upload a file
    file_id = await storage.upload(
        file_path="document.pdf",
        metadata={"source": "demo", "type": "pdf"}
    )
    print(f"File stored with ID: {file_id}")
    
    # Retrieve file info
    file_info = await storage.get_info(file_id)
    print(f"File size: {file_info['size']} bytes")
    print(f"Storage location: {file_info['path']}")
    
    # Layer 2: Content Extraction
    print("\n=== Layer 2: Content Extraction ===")
    extractor = ContentExtractor()
    
    # Extract content using OCR
    extraction_result = await extractor.extract(
        file_id=file_id,
        methods=["ocr", "text_extraction"]
    )
    print(f"Extraction job ID: {extraction_result['job_id']}")
    
    # Wait for extraction to complete
    while True:
        status = await extractor.get_status(extraction_result['job_id'])
        print(f"Extraction status: {status['state']}")
        
        if status['state'] == 'completed':
            break
        elif status['state'] == 'failed':
            print(f"Extraction failed: {status['error']}")
            return
        
        await asyncio.sleep(2)
    
    # Get extracted content
    content = await extractor.get_content(file_id)
    print(f"Text content length: {len(content['text'])} characters")
    print(f"Detected language: {content['language']}")
    print(f"Page count: {content['pages']}")
    
    # Layer 3: Knowledge Base Indexing
    print("\n=== Layer 3: Knowledge Base ===")
    kb = KnowledgeBase("demo_kb")
    
    # Create chunks from content
    chunks = await kb.create_chunks(
        content=content['text'],
        strategy="semantic",
        chunk_size=512,
        overlap=64
    )
    print(f"Created {len(chunks)} chunks")
    
    # Generate embeddings
    embeddings = await kb.generate_embeddings(chunks)
    print(f"Generated {len(embeddings)} embedding vectors")
    
    # Index in vector database
    index_result = await kb.index_document(
        file_id=file_id,
        chunks=chunks,
        embeddings=embeddings
    )
    print(f"Indexed document with {index_result['chunk_count']} chunks")
    
    # Search example
    search_results = await kb.search(
        query="What is the main topic?",
        limit=5
    )
    print(f"\nSearch returned {len(search_results)} relevant chunks")

# Run the demonstration
if __name__ == "__main__":
    asyncio.run(demonstrate_architecture())
```

### 2.2 Module Structure

```
unifiles/
├── app/                    # FastAPI application
│   ├── v1/                # API version 1
│   │   ├── main.py       # Application entry point
│   │   ├── routers/      # API endpoints
│   │   ├── schemas.py    # Pydantic models
│   │   └── middlewares.py # Custom middleware
├── core/                  # Core business logic
│   ├── database/         # Database models and managers
│   ├── ocr/             # OCR processing
│   ├── processors/      # Document processors
│   └── utils/           # Utility functions
├── client/              # Python client library
│   ├── client.py       # Main client class
│   └── models.py       # Client data models
└── tests/              # Test suite
    ├── unit/           # Unit tests
    ├── integration/    # Integration tests
    └── fixtures/       # Test fixtures
```

---

## Part 3: Writing and Running Tests

### 3.1 Unit Test Example

Create `tests/unit/test_file_storage.py`:

```python
import pytest
from unittest.mock import Mock, patch
from unifiles.core.storage import FileStorage

class TestFileStorage:
    """Unit tests for FileStorage class"""
    
    @pytest.fixture
    def storage(self):
        """Create a FileStorage instance for testing"""
        return FileStorage(base_path="/tmp/test_storage")
    
    @pytest.fixture
    def mock_file(self, tmp_path):
        """Create a temporary test file"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content here")
        return str(test_file)
    
    def test_upload_file_success(self, storage, mock_file):
        """Test successful file upload"""
        # Arrange
        expected_id = "file_123abc"
        
        with patch.object(storage, '_generate_id', return_value=expected_id):
            # Act
            file_id = storage.upload(mock_file)
            
            # Assert
            assert file_id == expected_id
            assert storage.exists(file_id)
    
    def test_upload_file_not_found(self, storage):
        """Test upload with non-existent file"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            storage.upload("/non/existent/file.pdf")
    
    def test_get_file_info(self, storage, mock_file):
        """Test retrieving file information"""
        # Arrange
        file_id = storage.upload(mock_file)
        
        # Act
        info = storage.get_info(file_id)
        
        # Assert
        assert info['id'] == file_id
        assert info['filename'] == "test.pdf"
        assert info['size'] > 0
        assert 'upload_time' in info
    
    @pytest.mark.parametrize("file_ext,expected_type", [
        (".pdf", "application/pdf"),
        (".txt", "text/plain"),
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ])
    def test_detect_file_type(self, storage, tmp_path, file_ext, expected_type):
        """Test file type detection for different extensions"""
        # Arrange
        test_file = tmp_path / f"test{file_ext}"
        test_file.write_bytes(b"content")
        
        # Act
        detected_type = storage._detect_mime_type(str(test_file))
        
        # Assert
        assert detected_type == expected_type
```

### 3.2 Integration Test Example

Create `tests/integration/test_document_processing.py`:

```python
import pytest
import asyncio
from pathlib import Path
from unifiles.client import Unifile

@pytest.mark.integration
class TestDocumentProcessing:
    """Integration tests for complete document processing flow"""
    
    @pytest.fixture
    async def client(self):
        """Create test client"""
        return Unifile(
            api_key="test_api_key",
            base_url="http://localhost:8087"
        )
    
    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF for testing"""
        pdf_path = tmp_path / "sample.pdf"
        # Create minimal PDF content
        pdf_content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
        pdf_path.write_bytes(pdf_content)
        return str(pdf_path)
    
    @pytest.mark.asyncio
    async def test_complete_processing_flow(self, client, sample_pdf):
        """Test the complete three-layer processing flow"""
        # Step 1: Create knowledge base
        kb = await client.create_knowledge_base(
            name="Integration Test KB",
            description="Testing complete flow"
        )
        assert kb.kb_id is not None
        
        # Step 2: Upload document
        document = await client.upload_file(
            file_path=sample_pdf,
            is_public=False
        )
        assert document.file_id is not None
        
        # Step 3: Extract content
        extraction = await document.extract_content(mode="normal")
        assert extraction['status'] == "started"
        
        # Step 4: Wait for extraction
        success = await document.wait_for_extraction(timeout=60)
        assert success is True
        
        # Step 5: Get content
        content = await document.get_content()
        assert 'text_content' in content
        assert 'extraction_metadata' in content
        
        # Step 6: Index to knowledge base
        index_result = await document.index_to_knowledge_base(
            kb_id=kb.kb_id,
            chunk_strategy="semantic"
        )
        assert index_result['success'] is True
        assert index_result['chunk_count'] > 0
        
        # Step 7: Verify document in knowledge base
        documents = await kb.list_documents()
        assert len(documents) == 1
        assert documents[0]['file_id'] == document.file_id
    
    @pytest.mark.asyncio
    async def test_error_handling(self, client):
        """Test error handling in processing flow"""
        # Test with invalid file
        with pytest.raises(FileNotFoundError):
            await client.upload_file("/invalid/path.pdf")
        
        # Test with invalid knowledge base ID
        with pytest.raises(ValueError):
            document = Mock()
            document.file_id = "test_id"
            await document.index_to_knowledge_base("invalid_kb_id")
```

### 3.3 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=unifiles --cov-report=html

# Run specific test file
pytest tests/unit/test_file_storage.py

# Run tests matching pattern
pytest -k "test_upload"

# Run with verbose output
pytest -v

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests in parallel
pytest -n auto
```

---

## Part 4: Debugging Techniques

### 4.1 Debug Configuration

Create `debug_helper.py`:

```python
"""
Debug helper utilities for development
"""

import logging
import json
from typing import Any
from functools import wraps
import time

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

def debug_timer(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        logging.debug(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.debug(f"{func.__name__} took {end - start:.2f} seconds")
        return result
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

def debug_print_request(request_data: dict):
    """Pretty print API request data"""
    print("\n=== API Request ===")
    print(json.dumps(request_data, indent=2))
    print("==================\n")

def debug_print_response(response_data: dict):
    """Pretty print API response data"""
    print("\n=== API Response ===")
    print(f"Status: {response_data.get('status', 'N/A')}")
    print(f"Data: {json.dumps(response_data.get('data', {}), indent=2)}")
    print("===================\n")

class DebugClient(Unifile):
    """Extended client with debug capabilities"""
    
    def __init__(self, *args, debug=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug = debug
    
    async def _make_request(self, method, endpoint, **kwargs):
        """Override to add debug logging"""
        if self.debug:
            debug_print_request({
                'method': method,
                'endpoint': endpoint,
                'params': kwargs
            })
        
        response = await super()._make_request(method, endpoint, **kwargs)
        
        if self.debug:
            debug_print_response(response)
        
        return response

# Usage example
if __name__ == "__main__":
    # Use debug client
    client = DebugClient(
        api_key="test_key",
        base_url="http://localhost:8087",
        debug=True
    )
    
    # All requests will now be logged
    kb = client.create_knowledge_base(name="Debug Test")
```

### 4.2 Common Debugging Scenarios

#### Debugging OCR Issues

```python
# debug_ocr.py
import asyncio
from unifiles.core.ocr import OCRProcessor

async def debug_ocr_processing(file_path: str):
    """Debug OCR processing step by step"""
    processor = OCRProcessor(debug=True)
    
    # Step 1: Validate file
    print(f"Validating file: {file_path}")
    is_valid = processor.validate_file(file_path)
    print(f"File valid: {is_valid}")
    
    if not is_valid:
        errors = processor.get_validation_errors()
        print(f"Validation errors: {errors}")
        return
    
    # Step 2: Pre-process
    print("\nPre-processing document...")
    preprocessed = await processor.preprocess(file_path)
    print(f"Pre-processing result: {preprocessed}")
    
    # Step 3: OCR extraction
    print("\nRunning OCR...")
    result = await processor.extract_text(preprocessed['path'])
    
    # Step 4: Analyze results
    print("\n=== OCR Results ===")
    print(f"Success: {result['success']}")
    print(f"Page count: {result['pages']}")
    print(f"Text length: {len(result['text'])}")
    print(f"Confidence: {result['confidence']}")
    
    if result['warnings']:
        print(f"Warnings: {result['warnings']}")
    
    # Step 5: Post-process
    print("\nPost-processing...")
    final = await processor.postprocess(result)
    print(f"Final text length: {len(final['text'])}")
    
    return final

# Run debug
asyncio.run(debug_ocr_processing("problem_document.pdf"))
```

#### Debugging Database Issues

```python
# debug_database.py
from unifiles.core.database import DatabaseManager
import logging

# Enable SQL logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

def debug_database_operations():
    """Debug database operations"""
    db = DatabaseManager(echo=True)  # Enable SQL echo
    
    # Test connection
    print("Testing database connection...")
    is_connected = db.test_connection()
    print(f"Connected: {is_connected}")
    
    if not is_connected:
        print("Connection failed. Checking configuration...")
        config = db.get_config()
        print(f"Database URL: {config['url']}")
        print(f"Pool size: {config['pool_size']}")
        return
    
    # Test query
    print("\nTesting query execution...")
    try:
        result = db.execute("SELECT 1")
        print(f"Query successful: {result}")
    except Exception as e:
        print(f"Query failed: {e}")
    
    # Check table existence
    print("\nChecking tables...")
    tables = db.get_tables()
    for table in tables:
        print(f"  - {table}")
        row_count = db.count_rows(table)
        print(f"    Rows: {row_count}")

debug_database_operations()
```

---

## Part 5: Contributing Code

### 5.1 Development Workflow

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature-name

# 2. Make changes and test locally
# ... edit files ...
pytest tests/

# 3. Format code
black unifiles/
isort unifiles/

# 4. Run linters
flake8 unifiles/
mypy unifiles/

# 5. Commit with descriptive message
git add .
git commit -m "feat: add support for DOCX file processing

- Implement DOCX parser in processors module
- Add unit tests for DOCX extraction
- Update documentation"

# 6. Push to your fork
git push origin feature/your-feature-name

# 7. Create pull request on GitHub
```

### 5.2 Code Style Guidelines

```python
# good_code_example.py
"""
Module for demonstrating Unifiles code style guidelines.

This module shows the preferred coding patterns and conventions
used throughout the Unifiles codebase.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import asyncio
import logging

from unifiles.core.base import BaseProcessor
from unifiles.core.exceptions import ProcessingError

logger = logging.getLogger(__name__)


class DocumentProcessor(BaseProcessor):
    """
    Process documents following Unifiles conventions.
    
    Attributes:
        config: Processor configuration
        cache: Internal cache for processed documents
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the document processor.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__()
        self.config = config or self._default_config()
        self.cache: Dict[str, Any] = {}
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "max_file_size": 100_000_000,  # 100MB
            "supported_formats": ["pdf", "docx", "txt"],
            "enable_cache": True,
        }
    
    async def process(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a document file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing processing results
            
        Raises:
            ProcessingError: If processing fails
            FileNotFoundError: If file doesn't exist
        """
        # Validate input
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check cache
        cache_key = str(file_path)
        if self.config["enable_cache"] and cache_key in self.cache:
            logger.debug(f"Returning cached result for {file_path}")
            return self.cache[cache_key]
        
        try:
            # Process the document
            result = await self._process_internal(file_path)
            
            # Cache result
            if self.config["enable_cache"]:
                self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Processing failed for {file_path}: {e}")
            raise ProcessingError(f"Failed to process {file_path}") from e
    
    async def _process_internal(self, file_path: Path) -> Dict[str, Any]:
        """Internal processing implementation."""
        # Implementation details here
        await asyncio.sleep(0.1)  # Simulate processing
        
        return {
            "status": "success",
            "file": str(file_path),
            "content": "Processed content here",
            "metadata": {
                "pages": 10,
                "words": 5000,
            }
        }
```

### 5.3 Writing Documentation

```python
# documentation_example.py
"""
Example of comprehensive documentation for Unifiles modules.

This module demonstrates the documentation standards including:
- Module docstrings
- Class docstrings
- Method docstrings with type hints
- Inline comments for complex logic
"""


def process_document(
    file_path: str,
    options: Optional[Dict[str, Any]] = None,
    callback: Optional[Callable[[str], None]] = None
) -> ProcessingResult:
    """
    Process a document with the specified options.
    
    This function handles the complete document processing pipeline,
    including validation, extraction, and indexing.
    
    Args:
        file_path: Path to the document file to process.
            Must be an absolute path to an existing file.
        options: Optional processing options. Supported keys:
            - 'ocr_enabled' (bool): Enable OCR processing. Default: True
            - 'chunk_size' (int): Size of text chunks. Default: 512
            - 'language' (str): Document language. Default: 'auto'
        callback: Optional callback function called with status updates.
            The callback receives a status string as its only argument.
    
    Returns:
        ProcessingResult object containing:
            - extracted_text (str): The extracted text content
            - metadata (dict): Document metadata
            - chunks (List[str]): Text chunks for indexing
            - embeddings (List[List[float]]): Vector embeddings
    
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        ValueError: If options contain invalid values
        ProcessingError: If document processing fails
    
    Examples:
        Basic usage:
        >>> result = process_document("/path/to/document.pdf")
        >>> print(result.extracted_text[:100])
        
        With options:
        >>> result = process_document(
        ...     "/path/to/document.pdf",
        ...     options={'ocr_enabled': True, 'chunk_size': 256}
        ... )
        
        With callback:
        >>> def status_callback(status: str):
        ...     print(f"Processing status: {status}")
        >>> result = process_document(
        ...     "/path/to/document.pdf",
        ...     callback=status_callback
        ... )
    
    Note:
        Large files (>100MB) may take several minutes to process.
        Consider using async version for better performance.
    """
    # Implementation here
    pass
```

---

## Summary

You've learned:
- How to set up a complete development environment
- The three-layer architecture and module structure
- Writing and running tests effectively
- Debugging techniques for common issues
- Contributing code following project standards

## Next Steps

1. **Explore Advanced Features**: Check the [Integration Tutorial](../first-upload.md)
2. **Deploy to Production**: See the [Deployment Guide](../../deployment.md)
3. **Join the Community**: Contribute to the project on GitHub
4. **Build Something**: Create your own document processing application

## Quick Reference

### Essential Commands

```bash
# Start development server
uvicorn unifiles.app.v1.main:app --reload

# Run tests
pytest

# Format code
black unifiles/ && isort unifiles/

# Check code quality
flake8 unifiles/ && mypy unifiles/

# Generate coverage report
pytest --cov=unifiles --cov-report=html
```

### Key Files

- `unifiles/app/v1/main.py` - API entry point
- `unifiles/core/` - Core business logic
- `unifiles/client/client.py` - Python client
- `tests/` - Test suite
- `config.yaml` - Configuration file

## Resources

- [API Documentation](http://localhost:8087/docs)
- [Architecture Diagram](../../../ARCHITECTURE.md)
- [Contributing Guidelines](../../../CONTRIBUTING.md)