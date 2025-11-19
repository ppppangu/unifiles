import uuid
from datetime import datetime
from typing import List

import asyncpg
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)
from fastapi import (
    Path as FastAPIPath,
)

from unifiles.core.logging import get_logger

logger = get_logger()

from unifiles.app.schemas import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    ProcessedDocument,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    StandardResponse,
    KnowledgeBaseDocumentsResponse,
)
from unifiles.core.database import (
    UnifiedKnowledgeBaseDBManager,
    unified_kb_db_manager,
    unified_user_db_manager,
)
from unifiles.core.database import extraction_db_manager
from unifiles.core.database.models import KnowledgeBaseModel
from unifiles.core.services.document_indexing_service import get_document_indexing_service

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])


def _model_to_info(kb_model: KnowledgeBaseModel) -> KnowledgeBaseInfo:
    """将数据库模型转换为API响应模型"""
    if kb_model.created_at:
        created_at = kb_model.created_at.isoformat()
    else:
        created_at = datetime.now().isoformat()

    if kb_model.updated_at:
        updated_at = kb_model.updated_at.isoformat()
    else:
        updated_at = created_at

    return KnowledgeBaseInfo(
        kb_id=kb_model.id,
        name=kb_model.name,
        description=kb_model.description or "",
        user_id=kb_model.user_id,
        document_count=kb_model.document_count or 0,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.post("", response_model=KnowledgeBaseCreateResponse, status_code=201)
async def create_knowledge_base(
    request: Request, create_request: KnowledgeBaseCreateRequest
):
    """创建新的知识库"""
    try:
        user_id = request.state.user_id
        client_ip = getattr(request.state, 'client_ip', 'unknown')
        logger.info(f"POST /knowledge-bases request from user: {user_id}")
        logger.debug(f"Create request payload: {create_request.dict()}")
        logger.debug(f"Request state: user_id={user_id}, client_ip={client_ip}")

        kb_name = create_request.name.strip()
        if not kb_name:
            raise HTTPException(
                status_code=400, detail="Knowledge base name is empty"
            )

        # Ensure user exists before creating knowledge base
        logger.debug(f"Ensuring user {user_id} exists in database")
        await unified_user_db_manager.ensure_user_exists(user_id)
        logger.debug(f"User {user_id} verified/created successfully")

        kb_id = f"kb_{uuid.uuid4().hex}"
        logger.debug(f"Generated kb_id: {kb_id}")

        kb_model = KnowledgeBaseModel(
            id=kb_id,
            user_id=user_id,
            name=kb_name,
            description=create_request.description or "",
        )
        logger.debug(f"KnowledgeBaseModel created: id={kb_model.id}, name={kb_model.name}, user_id={kb_model.user_id}")

        logger.debug(f"Calling database create_knowledge_base for {kb_id}")
        created_kb = await unified_kb_db_manager.create_knowledge_base(kb_model)
        logger.debug(f"Database operation completed for {kb_id}")
        kb_info = _model_to_info(created_kb)

        logger.info(f"Knowledge base created successfully: {kb_id}")
        return KnowledgeBaseCreateResponse(
            success=True,
            message="Knowledge base created successfully",
            knowledge_base=kb_info,
        )

    except HTTPException:
        raise
    except asyncpg.exceptions.UniqueViolationError as e:
        logger.warning(f"Knowledge base ID collision detected during creation: {e}")
        raise HTTPException(
            status_code=409,
            detail="Knowledge base with the same ID already exists",
        )
    except (asyncpg.PostgresError, OSError) as e:
        logger.exception(f"Database error creating knowledge base: {e}")
        logger.debug(f"KB model that failed: id={kb_id if 'kb_id' in locals() else 'not_generated'}, user_id={user_id}")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable while creating knowledge base",
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating knowledge base: {e}")
        logger.debug(f"Request context: user_id={user_id}, kb_name={kb_name if 'kb_name' in locals() else 'not_set'}")
        raise HTTPException(
            status_code=500, detail=f"Knowledge base creation failed: {e!s}"
        )


@router.get("", response_model=KnowledgeBaseListResponse)
async def get_knowledge_bases(
    request: Request,
    limit: int = 50,
    offset: int = 0,
):
    """获取用户的知识库列表（真实查询）"""
    try:
        user_id = request.state.user_id
        logger.info(
            f"GET /knowledge-bases request from user: {user_id}, limit={limit}, offset={offset}"
        )

        # 查询数据库
        kb_models, total_count = await unified_kb_db_manager.list_knowledge_bases(
            user_id=user_id, limit=limit, offset=offset
        )

        kb_list: List[KnowledgeBaseInfo] = [
            _model_to_info(m) for m in kb_models
        ]

        has_more = (offset + len(kb_list)) < total_count

        return KnowledgeBaseListResponse(
            success=True,
            message="Knowledge bases retrieved successfully",
            knowledge_bases=kb_list,
            total_count=total_count,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error listing knowledge bases: {e}")
        raise HTTPException(
            status_code=503, detail="Database unavailable while listing knowledge bases"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing knowledge bases: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list knowledge bases: {e!s}"
        )


@router.get("/{kb_id}", response_model=KnowledgeBaseInfo)
async def get_knowledge_base_info(
    request: Request, kb_id: str = FastAPIPath(..., description="知识库ID")
):
    """获取知识库信息"""
    user_id = request.state.user_id
    logger.info(f"GET /knowledge-bases/{kb_id} request from user: {user_id}")
    # TODO: Implement logic to get KB info from database
    raise HTTPException(
        status_code=501,
        detail="Get knowledge base info functionality not implemented yet",
    )


@router.delete("/{kb_id}", response_model=StandardResponse)
async def delete_knowledge_base(
    request: Request, kb_id: str = FastAPIPath(..., description="知识库ID")
):
    """删除知识库及其关联数据"""
    try:
        user_id = request.state.user_id
        logger.info(f"DELETE /knowledge-bases/{kb_id} request from user: {user_id}")

        # 1. 验证知识库存在且用户有权限
        kb = await unified_kb_db_manager.get_knowledge_base(kb_id)
        if not kb:
            logger.warning(f"Knowledge base not found: {kb_id}")
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if kb.user_id != user_id:
            logger.warning(
                f"Access denied: KB {kb_id} belongs to user {kb.user_id}, "
                f"requested by {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: you do not own this knowledge base",
            )

        # 2. 删除知识库（依赖数据库层级联删除文档及组件）
        delete_result = await unified_kb_db_manager.delete_knowledge_base(kb_id)

        return StandardResponse(
            success=True,
            message="Knowledge base deleted successfully",
            data={"kb_id": kb_id, **delete_result},
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error deleting knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable while deleting knowledge base",
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete knowledge base: {e!s}"
        )


@router.post("/{kb_id}/documents", response_model=ProcessDocumentResponse)
async def index_extracted_content_to_knowledge_base(
    request: Request,
    process_request: ProcessDocumentRequest,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
):
    """将已提取的内容索引到知识库

    完整流程：
    1. 验证知识库和提取文档的存在性及权限
    2. 调用索引服务进行分块、嵌入、存储
    3. 返回索引结果

    Args:
        request: FastAPI请求对象（包含user_id）
        process_request: 处理请求（包含extraction_id和chunk_strategy）
        kb_id: 知识库ID

    Returns:
        ProcessDocumentResponse: 处理结果，包含document_id和chunk_count

    Raises:
        HTTPException: 404 - 知识库或提取文档不存在
        HTTPException: 403 - 权限不足
        HTTPException: 500 - 索引失败
    """
    try:
        user_id = request.state.user_id
        logger.info(
            f"POST /knowledge-bases/{kb_id}/documents from user: {user_id}, "
            f"extraction_id: {process_request.extraction_id}"
        )

        # 1. 验证知识库存在且用户有权限
        kb = await unified_kb_db_manager.get_knowledge_base(kb_id)
        if not kb:
            logger.warning(f"Knowledge base not found: {kb_id}")
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if kb.user_id != user_id:
            logger.warning(
                f"Access denied: KB {kb_id} belongs to user {kb.user_id}, "
                f"requested by {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: you do not own this knowledge base",
            )

        # 2. 验证提取文档存在且用户有权限
        extracted_doc = await extraction_db_manager.get_extracted_document(
            process_request.extraction_id, user_id
        )
        if not extracted_doc:
            logger.warning(
                f"Extraction not found: {process_request.extraction_id} for user {user_id}"
            )
            raise HTTPException(
                status_code=404,
                detail="Extraction not found or access denied",
            )

        # 3. 调用索引服务
        indexing_service = get_document_indexing_service()
        result = await indexing_service.index_extracted_document_to_kb(
            extraction_id=process_request.extraction_id,
            kb_id=kb_id,
            user_id=user_id,
            chunk_strategy=process_request.chunk_strategy,
        )

        # 4. 构建响应
        processed_doc = ProcessedDocument(
            document_id=result["document_id"],
            extraction_id=process_request.extraction_id,
            knowledge_base_id=kb_id,
            chunk_count=result["chunk_count"],
            indexing_status=result["indexing_status"],
            created_at=result["created_at"],
        )

        logger.info(
            f"Document indexed successfully: document_id={result['document_id']}, "
            f"chunks={result['chunk_count']}"
        )

        return ProcessDocumentResponse(
            success=True,
            message="Document indexed successfully to knowledge base",
            document=processed_doc,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error indexing document to KB {kb_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.error(f"Permission error indexing document to KB {kb_id}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error indexing document to KB {kb_id}")
        raise HTTPException(
            status_code=500, detail=f"Document indexing failed: {e!s}"
        )


@router.get("/{kb_id}/documents", response_model=KnowledgeBaseDocumentsResponse)
async def get_knowledge_base_documents(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
    limit: int = 50,
    offset: int = 0,
):
    """获取知识库文档列表"""
    try:
        user_id = request.state.user_id
        logger.info(
            f"GET /knowledge-bases/{kb_id}/documents request from user: {user_id}, "
            f"limit={limit}, offset={offset}"
        )

        # 简单参数校验（允许稍大分页以便人工检查）
        if limit < 1 or limit > 200:
            raise HTTPException(
                status_code=400, detail="Limit must be between 1 and 200"
            )
        if offset < 0:
            raise HTTPException(status_code=400, detail="Offset must be non-negative")

        # 1. 验证知识库存在且用户有权限
        kb = await unified_kb_db_manager.get_knowledge_base(kb_id)
        if not kb:
            logger.warning(f"Knowledge base not found: {kb_id}")
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if kb.user_id != user_id:
            logger.warning(
                f"Access denied: KB {kb_id} belongs to user {kb.user_id}, "
                f"requested by {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: you do not own this knowledge base",
            )

        # 2. 查询知识库文档列表
        doc_models, total_count = await unified_kb_db_manager.list_documents(
            kb_id, limit=limit, offset=offset
        )

        documents: List[ProcessedDocument] = []
        for m in doc_models:
            # created_at 可能为 None，使用当前时间字符串作为回退
            created_at = (
                m.created_at.isoformat()
                if getattr(m, "created_at", None)
                else datetime.now().isoformat()
            )
            documents.append(
                ProcessedDocument(
                    document_id=m.id,
                    extraction_id=m.extracted_document_id,
                    knowledge_base_id=m.knowledge_base_id,
                    chunk_count=m.chunk_count or 0,
                    indexing_status=m.indexing_status,
                    created_at=created_at,
                )
            )

        has_more = (offset + len(documents)) < total_count

        return KnowledgeBaseDocumentsResponse(
            success=True,
            message="Knowledge base documents retrieved successfully",
            documents=documents,
            total_count=total_count,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error listing documents in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable while listing knowledge base documents",
        )
    except Exception as e:
        logger.error(f"Unexpected error listing documents in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list knowledge base documents: {e!s}",
        )


@router.delete("/{kb_id}/documents/{doc_id}", response_model=StandardResponse)
async def delete_knowledge_base_document(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
    doc_id: str = FastAPIPath(..., description="文档ID"),
):
    """删除知识库文档"""
    user_id = request.state.user_id
    logger.info(f"DELETE /kbs/{kb_id}/documents/{doc_id} from user: {user_id}")
    # TODO: Implement logic to delete a document and its vectors from a KB
    raise HTTPException(
        status_code=501,
        detail="Delete knowledge base document functionality not implemented yet",
    )


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge_base(
    request: Request,
    search_request: SearchRequest,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
):
    """在知识库中进行向量检索

    需要认证（AuthMiddleware自动处理）

    工作流程:
    1. 验证用户权限（知识库是否属于该用户）
    2. 生成查询文本的向量表示
    3. 执行向量相似度检索
    4. 返回按相似度排序的结果

    Args:
        request: FastAPI请求对象（包含user_id）
        search_request: 检索请求（包含query和top_k）
        kb_id: 知识库ID

    Returns:
        SearchResponse: 检索结果，包含相似度分数和文本内容

    Raises:
        HTTPException: 404 - 知识库不存在或无权访问
        HTTPException: 400 - 查询参数无效
        HTTPException: 500 - 检索失败
    """
    try:
        user_id = request.state.user_id
        logger.info(
            f"POST /knowledge-bases/{kb_id}/search from user: {user_id}, "
            f"query='{search_request.query[:50]}...', top_k={search_request.top_k}"
        )

        # 1. 验证知识库存在且用户有权限
        kb = await unified_kb_db_manager.get_knowledge_base(kb_id)
        if not kb:
            logger.warning(f"Knowledge base not found: {kb_id}")
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if kb.user_id != user_id:
            logger.warning(
                f"Access denied: KB {kb_id} belongs to user {kb.user_id}, "
                f"requested by {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: you do not own this knowledge base",
            )

        # 2. 调用检索服务
        from unifiles.core.services.search_service import get_search_service

        search_service = get_search_service()
        results = await search_service.search(
            kb_id=kb_id, query=search_request.query, top_k=search_request.top_k
        )

        # 3. 格式化响应
        result_items = [
            SearchResultItem(
                chunk_id=r["chunk_id"],
                component_id=r["component_id"],
                document_id=r["document_id"],
                text_content=r["text_content"],
                similarity_score=r["similarity_score"],
            )
            for r in results
        ]

        logger.info(
            f"Search completed for KB {kb_id}: returned {len(result_items)} results"
        )

        return SearchResponse(
            success=True,
            message=f"Found {len(result_items)} results",
            results=result_items,
            total_results=len(result_items),
            query=search_request.query,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Search validation error for KB {kb_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error during search in KB {kb_id}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}")
