# Unifiles Python Client SDK User Guide

The Unifiles Python Client SDK provides a simple and powerful way to interact with the Unifiles document processing service. It allows you to easily upload files, extract content (OCR), and build knowledge bases with vector search capabilities.

## Installation

Install the client SDK using pip:

```bash
pip install unifiles-client
```

## Quick Start

Here is a complete example to get you started. This script uploads a file, extracts its content, indexes it into a knowledge base, and performs a search.

```python
from unifiles_client import Unifiles

# 1. Initialize the client
client = Unifiles(
    api_key="your-api-key", 
    base_url="http://localhost:8088"
)

# 2. Create a Knowledge Base
kb = client.create_knowledge_base(
    name="My Knowledge Base", 
    description="A collection of important documents"
)
print(f"Created Knowledge Base: {kb.name} ({kb.kb_id})")

# 3. Upload, Extract, and Index a Document
# This helper method handles the entire pipeline automatically
document = kb.upload_document(
    file_path="path/to/your/document.pdf",
    auto_extract=True,
    auto_index=True
)
print(f"Document processed: {document.filename}")

# 4. Search the Knowledge Base
# Text-only search
results = kb.search("What is the main topic of this document?", top_k=3)

print("\nText Search Results:")
for result in results:
    print(f"- [{result.similarity_score:.3f}] {result.text_content[:100]}...")

# Text + image search (include photo components)
image_results = kb.search(
    "What is shown in the diagrams?", top_k=3, include_photos=True
)

print("\nMixed (Text + Image) Search Results:")
for result in image_results:
    print(f"- [{result.similarity_score:.3f}] {result.text_content[:100]}...")
```

## Core Concepts: The Three-Layer Architecture

Unifiles is built around a "Three-Layer Architecture" that gives you granular control over how your documents are processed.

1.  **File Storage Layer**:
    *   **What it is**: The raw file storage.
    *   **Action**: Upload your original files (PDF, Images, Office docs, etc.).
    *   **Result**: A `Document` object with a `file_id`.

2.  **Content Extraction Layer**:
    *   **What it is**: The process of converting raw files into machine-readable text and images (OCR).
    *   **Action**: Call `extract_content()` on a document.
    *   **Result**: The document gains "extracted content" (text and markdown).

3.  **Knowledge Base Indexing Layer**:
    *   **What it is**: The intelligent layer where content is chunked, vectorized, and stored for search.
    *   **Action**: Call `index_to_knowledge_base()` on a document.
    *   **Result**: The document is searchable within a specific `KnowledgeBase`.

## Usage Guide

### 1. Client Initialization

First, import `Unifiles` and create an instance with your API key and the server URL.

```python
from unifiles_client import Unifiles

client = Unifiles(api_key="your_api_key", base_url="http://localhost:8088")
```

### 2. File Management

You can upload files directly to the storage layer without processing them immediately.

```python
# Upload a file
doc = client.upload_file("contract.pdf")
print(f"Uploaded {doc.filename} (ID: {doc.file_id})")

# List all files
files = client.list_files(limit=10)
for f in files:
    print(f.filename)

# Delete a file
client.delete_file(doc.file_id)
```

### 3. Content Extraction

To make a file useful, you need to extract its content. This is an asynchronous operation, but the SDK handles the waiting for you if you ask it to.

```python
from unifiles_client import ContentType

# Upload
doc = client.upload_file("scan.png")

# Extract content (wait for completion)
task_result = doc.extract_content(mode="simple", wait=True)

# Recommended: use get_content() helper
text_content = doc.get_content(ContentType.TEXT)["content"]
print(text_content)
```

When `wait=True`, `extract_content()` returns the task result object from `/tasks/{task_id}/result`, 
and the SDK also caches the extracted content internally so that `get_content()` can be used afterwards.

**Extraction Modes:**
*   `simple`: Basic text extraction using the default OCR / parsing pipeline.
*   `selfhosted`: Use a self-hosted OCR / multimodal model (requires server configuration).
*   `mistral`: Use a Mistral-based LLM OCR/extraction backend (requires configuration).
*   `openai`: Use an OpenAI-compatible OCR/extraction backend (requires configuration).

#### Image Content Parsing (selfhosted mode only)

When using `selfhosted` mode, you can control whether to generate semantic descriptions for images and tables in the document via the `parse_image_content` parameter:

```python
# Basic extraction - images use simple labels
doc = client.upload_file("report.pdf")
result = doc.extract_content(
    mode="selfhosted",
    parse_image_content=False,  # Default value
    wait=True
)
# In Markdown: ![Picture](picture_1_0.png)

# Full extraction - images use AI-generated descriptions
result = doc.extract_content(
    mode="selfhosted",
    parse_image_content=True,  # Enable image content parsing
    wait=True,
    timeout=600  # Recommend increasing timeout
)
# In Markdown: ![Product design diagram showing three views of the new smartphone](picture_1_0.png)
```

**Important Notes**:
- `parse_image_content` is only effective when `mode="selfhosted"`, other modes will ignore it
- Generating descriptions for each image/table increases processing time (~2-3x) and API call costs (~2-3x)
- Image descriptions make full-text search more accurate, suitable for important documents and knowledge bases
- If `parse_image_content=True` is set with a non-selfhosted mode, the SDK will raise a `ValueError`

**Performance Comparison Example**:

```python
import time

doc = client.upload_file("document_with_images.pdf")

# Fast mode
start = time.time()
doc.extract_content(mode="selfhosted", parse_image_content=False, wait=True)
print(f"Fast mode: {time.time() - start:.1f}s")

# Full mode
start = time.time()
doc.extract_content(mode="selfhosted", parse_image_content=True, wait=True)
print(f"Full mode: {time.time() - start:.1f}s")
```

### 4. Knowledge Base Management

Knowledge Bases are containers for your indexed documents.

```python
# Create a KB
kb = client.create_knowledge_base("Finance Docs")

# Get an existing KB
kb = client.get_knowledge_base("kb_12345")

# List KBs
kbs = client.list_knowledge_bases()
```

### 5. Indexing and Search

The most common workflow is to add documents to a Knowledge Base and then search them.

```python
# Add a document to KB (handles upload -> extract -> index)
doc = kb.upload_document("report.pdf")

# Search
results = kb.search("quarterly revenue", top_k=5)
for res in results:
    print(res.text_content)
```

## API Reference

### `Unifiles` Client

The main SDK entry point is the `Unifiles` class (exported from the `unifiles_client` package):

```python
from unifiles_client import Unifiles
```

Key methods:

*   `upload_file(file_path, is_public=False) -> Document`: Uploads a file to the storage layer.
*   `get_document(file_id) -> Document`: Gets a `Document` instance by ID.
*   `list_files(limit=50, offset=0) -> List[Document]`: Lists uploaded files for the current user.
*   `delete_file(file_id) -> bool`: Deletes a file; returns `True` on success.
*   `create_knowledge_base(name, description="") -> KnowledgeBase`: Creates a new `KnowledgeBase`.
*   `get_knowledge_base(kb_id) -> KnowledgeBase`: Gets a `KnowledgeBase` instance by ID (lazy-loading info when needed).
*   `list_knowledge_bases(limit=50, offset=0) -> List[KnowledgeBase]`: Lists the current user's knowledge bases.
*   `delete_knowledge_base(kb_id) -> bool`: Deletes a knowledge base; returns `True` on success.
*   `quick_process(file_path, knowledge_base_name=None, extract_mode="simple") -> Document`:
    Convenience helper that uploads a file, triggers extraction, and (optionally) indexes into a named knowledge base.

### `Document` Class

Represents a single file and its processing state.

*   `extract_content(mode="simple", parse_image_content=False, wait=False, timeout=300, poll_interval=5)`: 
    Starts the OCR/extraction process.
    - `mode`: Extraction mode (simple|selfhosted|mistral|openai)
    - `parse_image_content`: Whether to parse image content to full_markdown (only effective for selfhosted mode, default False)
    - `wait`: Whether to wait for task completion (default False)
    - `timeout`: Wait timeout in seconds
    - `poll_interval`: Polling interval in seconds
    
    When `wait=True`, it waits for completion and returns the task result from `/tasks/{task_id}/result`, and also caches the extracted content inside the `Document`.
    
    **Note**: If `parse_image_content=True` but `mode != "selfhosted"`, a `ValueError` will be raised.

*   `get_content(content_type: Optional[ContentType] = None)`: Returns the extracted content dict; optionally filters by text/image via `ContentType.TEXT` or `ContentType.IMAGE`.
*   `index_to_knowledge_base(kb_id, chunk_strategy="markdown_hierarchical")`: Indexes the extracted content into a Knowledge Base using the specified chunking strategy.
*   `status`: Property that returns the current status (`UPLOADED`, `EXTRACTING`, `EXTRACTED`, `INDEXED`, `FAILED`).

### `KnowledgeBase` Class

Manages a collection of searchable documents.

*   `upload_document(file_path, is_public=False, auto_extract=True, auto_index=True, extract_mode="simple") -> Document`:
    Helper to upload and process a file in one go (upload → extract → index).
*   `search(query, top_k=10, include_photos=False) -> List[SearchResult]`: Performs a semantic search within this knowledge base. Set `include_photos=True` to also include image components (`component_type='photo'`) in the results.
*   `list_documents(limit=50, offset=0) -> List[dict]`: Lists documents in this Knowledge Base (requires server support for the corresponding endpoint).
*   `delete_document(document_id) -> bool`: Removes a document from the Knowledge Base (requires server endpoint support).
