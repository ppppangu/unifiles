"""
检索服务
提供知识库向量检索功能
"""

from typing import Any, Dict, List, Optional

from unifiles.core.logging import get_logger

logger = get_logger()

from ..database import unified_kb_db_manager
from .embedding_service import get_embedding_service


class SearchService:
    """检索服务主类 - 封装知识库检索逻辑"""

    def __init__(self):
        """初始化检索服务"""
        self.embedding_service = get_embedding_service()
        self.kb_manager = unified_kb_db_manager

    async def search(
        self, kb_id: str, query: str, top_k: int = 10, include_photos: bool = False
    ) -> List[Dict[str, Any]]:
        """在知识库中执行向量检索

        工作流程:
        1. 验证知识库存在
        2. 生成查询文本的向量表示
        3. 调用数据库进行向量相似度检索
        4. 返回排序后的检索结果

        Args:
            kb_id: 知识库ID
            query: 检索查询文本
            top_k: 返回结果数量，默认10
            include_photos: 是否包含图片块在检索结果中，默认False

        Returns:
            检索结果列表，每项包含：
            - component_id: 组件ID（统一主键）
            - document_id: 文档ID
            - text_content: 文本内容或图片描述
            - similarity_score: 相似度分数（0-1）
            - component_type: 组件类型（chunk或photo）

        Raises:
            ValueError: 如果知识库不存在或查询为空
            Exception: 检索过程中的其他错误
        """
        try:
            # 1. 验证输入
            if not query or not query.strip():
                raise ValueError("Search query cannot be empty")

            if top_k < 1 or top_k > 100:
                raise ValueError("top_k must be between 1 and 100")

            logger.info(
                f"Starting search for KB {kb_id}: query='{query[:50]}...', top_k={top_k}, include_photos={include_photos}"
            )

            # 2. 验证知识库存在
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                raise ValueError(f"Knowledge base not found: {kb_id}")

            logger.debug(f"Knowledge base verified: {kb.name}")

            # 3. 生成查询向量
            logger.debug("Generating query embedding...")
            query_embedding = await self.embedding_service.embed_single_text(query)
            logger.debug(f"Query embedding generated: dimension={len(query_embedding)}")

            # 4. 执行向量检索
            logger.debug("Performing vector search in database...")
            results = await self.kb_manager.search_knowledge_base_vector(
                kb_id=kb_id,
                query_embedding=query_embedding,
                top_k=top_k,
                include_photos=include_photos,
            )

            logger.info(
                f"Search completed for KB {kb_id}: found {len(results)} results"
            )

            return results

        except ValueError as e:
            logger.warning(f"Search validation error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Search failed for KB {kb_id}: {e}")
            raise


# 默认检索服务实例
_default_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """获取默认检索服务实例（单例模式）"""
    global _default_search_service
    if _default_search_service is None:
        _default_search_service = SearchService()
    return _default_search_service
