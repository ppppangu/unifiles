# Unifiles Python SDK Changelog

## 2025-12-17

### Added
- Added `KnowledgeBase.get_document_detail(document_id)` method to retrieve full document information including markdown content, file metadata, and extraction statistics
- Added `DocumentDetailDict` TypedDict for better type hints on document detail responses
- Added deprecation warning infrastructure using standard Python `warnings` module for future API evolution

### Improved
- Enhanced `KnowledgeBase.list_documents()` response documentation to include new fields: `original_filename`, `file_size`, `file_id` (server API already returns these)
- Improved type hints for better IDE autocomplete support
- Enhanced docstrings with detailed examples and field descriptions

### Documentation
- Added "Document Management" section to English SDK user guide (`docs/user-guide/client_sdk.md`)
- Added "文档管理" section to Chinese SDK user guide (`docs/user-guide/client_sdk_zh.md`)
- Updated API reference documentation with new methods and response fields
- Added usage examples for retrieving full document content

### Developer Notes
- The `get_document_detail()` method uses the new `GET /knowledge-bases/{kb_id}/documents/{doc_id}` endpoint (server API v1.1.0+)
- Enhanced metadata is retrieved via JOIN queries on server side (documents + extracted_documents + files tables)
- All changes maintain 100% backward compatibility with existing SDK code

## 2025-12-01

- Added `include_photos` parameter to `KnowledgeBase.search(query, top_k=10, include_photos=False)` in the Python client SDK to allow including image components (`component_type='photo'`) in search results.
- Updated English SDK user guide (`docs/user-guide/client_sdk.md`) to document the new `include_photos` parameter and to add examples for text-only and text+image search.
- Updated Chinese SDK user guide (`docs/user-guide/client_sdk_zh.md`) to document the new `include_photos` parameter and to add examples for文本检索和“文本 + 图片”联合检索。
