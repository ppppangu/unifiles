# Unifiles Python SDK Changelog

## 2025-12-01

- Added `include_photos` parameter to `KnowledgeBase.search(query, top_k=10, include_photos=False)` in the Python client SDK to allow including image components (`component_type='photo'`) in search results.
- Updated English SDK user guide (`docs/user-guide/client_sdk.md`) to document the new `include_photos` parameter and to add examples for text-only and text+image search.
- Updated Chinese SDK user guide (`docs/user-guide/client_sdk_zh.md`) to document the new `include_photos` parameter and to add examples for文本检索和“文本 + 图片”联合检索。
