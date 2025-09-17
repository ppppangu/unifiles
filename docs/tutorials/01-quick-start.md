# Unifiles Quick Start Guide (5-10 Minutes)

## What You'll Learn

- Install and set up Unifiles environment
- Start the API server
- Make your first API call
- Upload and process your first document
- Retrieve processed content

## Prerequisites

- Python 3.8 or higher
- Basic understanding of REST APIs
- 500MB free disk space for dependencies

## Time Estimate

- Setup: 3 minutes
- First API call: 2 minutes  
- Document processing: 5 minutes

## Final Result

By the end of this guide, you'll have:
- A running Unifiles server
- Successfully processed a document through all three layers
- Retrieved extracted content from your document

---

## Step 1: Installation and Setup

### 1.1 Clone the Repository

```bash
git clone https://github.com/unifiles/unifiles.git
cd unifiles
```

### 1.2 Install Dependencies

Using pip:
```bash
pip install -r requirements.txt
```

Or using uv (recommended for faster installation):
```bash
pip install uv
uv pip install -r requirements.txt
```

### 1.3 Configure Environment

Create a `.env` file in the project root:

```bash
# API Configuration
UNIFILES_API_KEY=[REDACTED]
UNIFILES_PORT=8087

# Optional: External Services (for production)
# MINIO_ENDPOINT=localhost:9000
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5437
```

**Checkpoint**: Run `python -c "import unifiles; print('Setup successful!')"` to verify installation.

---

## Step 2: Start the Server

### 2.1 Run the FastAPI Server

```bash
# Using uvicorn directly
uvicorn unifiles.app.v1.main:app --host 0.0.0.0 --port 8087 --reload

# Or using the Python module
python -m uvicorn unifiles.app.v1.main:app --host 0.0.0.0 --port 8087 --reload
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8087 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 2.2 Verify Server Health

Open a new terminal and run:

```bash
curl http://localhost:8087/health
```

Expected response:
```json
{
  "success": true,
  "message": "Service is healthy",
  "data": {
    "version": "1.1.0",
    "service": "unifiles-v1"
  }
}
```

**Checkpoint**: Visit http://localhost:8087/docs to see the interactive API documentation.

---

## Step 3: Your First API Call

### 3.1 Using Python Client

Create a file `first_call.py`:

```python
from unifiles.client import Unifile

# Initialize client
client = Unifile(
    api_key="[REDACTED]",
    base_url="http://localhost:8087"
)

# Create your first knowledge base
kb = client.create_knowledge_base(
    name="My First Knowledge Base",
    description="Testing Unifiles document processing"
)

print(f"Success! Created knowledge base: {kb.name}")
print(f"Knowledge Base ID: {kb.kb_id}")
```

Run it:
```bash
python first_call.py
```

### 3.2 Using cURL

```bash
curl -X POST "http://localhost:8087/api/v1/knowledge-bases" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Knowledge Base",
    "description": "Testing Unifiles document processing"
  }'
```

---

## Step 4: Upload and Process a Document

### 4.1 Prepare a Test Document

Create a simple test PDF or use any existing PDF file. For testing, you can create a text file:

```bash
echo "This is my test document for Unifiles processing." > test_document.txt
```

### 4.2 Upload and Process

Create `upload_document.py`:

```python
from unifiles.client import Unifile
from pathlib import Path

# Initialize client
client = Unifile(
    api_key="[REDACTED]",
    base_url="http://localhost:8087"
)

# Path to your document
document_path = "test_document.txt"  # or path to your PDF

# Quick process: Upload → Extract → Index in one call
print("Starting document processing...")
document = client.quick_process(
    file_path=document_path,
    knowledge_base_name="My First Knowledge Base"
)

print("Document processing complete!")
print(f"File ID: {document.file_id}")
print(f"Filename: {document.filename}")

# Check processing status
info = document.get_info()
print(f"Status: {info.get('status', 'Unknown')}")
```

Run it:
```bash
python upload_document.py
```

Expected output:
```
Starting document processing...
Document processing complete!
File ID: doc_abc123xyz
Filename: test_document.txt
Status: completed
```

---

## Step 5: Retrieve Processed Content

### 5.1 Get Extracted Content

Create `get_content.py`:

```python
from unifiles.client import Unifile, ContentType

# Initialize client
client = Unifile(
    api_key="[REDACTED]",
    base_url="http://localhost:8087"
)

# Get your knowledge base
kb_list = client.list_knowledge_bases()
if kb_list:
    kb = kb_list[0]
    print(f"Using knowledge base: {kb.name}")
    
    # Get documents in the knowledge base
    documents = kb.list_documents()
    
    if documents:
        # Get the first document's content
        doc_info = documents[0]
        document = client.get_document(doc_info['file_id'])
        
        # Retrieve all extracted content
        content = document.get_content()
        
        print("\n=== Extracted Content ===")
        print(f"Text Content: {content.get('text_content', 'N/A')[:200]}...")
        print(f"Extraction Metadata: {content.get('extraction_metadata', {})}")
        
        # Get specific content types
        text_only = document.get_content(ContentType.TEXT)
        print(f"\nText-only content length: {len(text_only.get('content', ''))}")
    else:
        print("No documents found in knowledge base")
```

Run it:
```bash
python get_content.py
```

---

## Troubleshooting

### Common Issues and Solutions

#### Port Already in Use
**Error**: `[Errno 48] Address already in use`

**Solution**:
```bash
# Find process using port 8087
lsof -i :8087  # On Mac/Linux
netstat -ano | findstr :8087  # On Windows

# Kill the process or use a different port
uvicorn unifiles.app.v1.main:app --port 8088
```

#### Import Error
**Error**: `ModuleNotFoundError: No module named 'unifiles'`

**Solution**:
```bash
# Add project to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or install in development mode
pip install -e .
```

#### Authentication Failed
**Error**: `401 Unauthorized`

**Solution**:
1. Check your API key in `.env` file
2. Ensure the Authorization header is correctly formatted
3. Verify the API key matches between client and server

#### Document Processing Timeout
**Error**: `Processing timeout after 300 seconds`

**Solution**:
```python
# Increase timeout for large documents
document.wait_for_extraction(timeout=600)  # 10 minutes
```

---

## Summary

You've successfully:
- Set up a Unifiles development environment
- Started the API server
- Created a knowledge base
- Uploaded and processed a document
- Retrieved extracted content

## Next Steps

1. **Explore the API Documentation**: Visit http://localhost:8087/docs
2. **Try Different File Types**: Upload PDFs, images, or Word documents
3. **Learn About the Three-Layer Architecture**: See the [Developer Tutorial](02-developer-tutorial.md)
4. **Set Up Production Environment**: Check the [Deployment Guide](04-deployment-guide.md)

## Additional Resources

- [API Reference Documentation](../api-reference.md)
- [Configuration Options](../configuration.md)
- [Examples Repository](../../examples/)