"""
Unifiles Python Client

简洁易用的文档处理客户端，支持三层文档处理架构：
1. 文件存储层：原始文件上传和管理
2. 内容提取层：OCR处理，生成图片类和文字类内容
3. 知识库索引层：文档分块和向量化

主要类：
- Unifile: 主客户端入口
- Document: 文档生命周期管理
- KnowledgeBase: 知识库管理
- SearchResult: 向量检索结果
"""

from .client import (
    AuthenticationError,
    ContentType,
    Document,
    DocumentNotFoundError,
    DocumentStatus,
    KnowledgeBase,
    KnowledgeBaseNotFoundError,
    RateLimitError,
    SearchResult,
    Unifiles,
    UnifilesError,
)

__version__ = "0.0.1"
__all__ = [
    "AuthenticationError",
    "ContentType",
    "Document",
    "DocumentNotFoundError",
    "DocumentStatus",
    "KnowledgeBase",
    "KnowledgeBaseNotFoundError",
    "RateLimitError",
    "SearchResult",
    "Unifiles",
    "UnifilesError",
]
