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
from loguru import logger

from unifiles.app.schemas import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    ProcessedDocument,
    StandardResponse,
)
from unifiles.core.database import (
    DatabaseManager as KnowledgeBaseDBManager,
    unified_user_db_manager,
)
from unifiles.core.database.models import KnowledgeBaseModel

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])

knowledge_db_manager = KnowledgeBaseDBManager()


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
        logger.info(f"POST /knowledge-bases request from user: {user_id}")
        logger.info(f"Create request payload: {create_request.dict()}")

        kb_name = create_request.name.strip()
        if not kb_name:
            raise HTTPException(
                status_code=400, detail="Knowledge base name is empty"
            )

        # Ensure user exists before creating knowledge base
        await unified_user_db_manager.ensure_user_exists(user_id)

        kb_id = f"kb_{uuid.uuid4().hex}"
        kb_model = KnowledgeBaseModel(
            id=kb_id,
            user_id=user_id,
            name=kb_name,
            description=create_request.description or "",
        )

        created_kb = await knowledge_db_manager.create_knowledge_base(kb_model)
        kb_info = _model_to_info(created_kb)

        logger.info(f"Knowledge base created successfully: {kb_id}")
        return KnowledgeBaseCreateResponse(
            success=True,
            message="Knowledge base created successfully",
            knowledge_base=kb_info,
        )

    except HTTPException:
        raise
    except asyncpg.exceptions.UniqueViolationError:
        logger.warning("Knowledge base ID collision detected during creation")
        raise HTTPException(
            status_code=409,
            detail="Knowledge base with the same ID already exists",
        )
    except (asyncpg.PostgresError, OSError) as e:
        logger.error(f"Database error creating knowledge base: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable while creating knowledge base",
        )
    except Exception as e:
        logger.error(f"Error creating knowledge base: {e}")
        raise HTTPException(
            status_code=500, detail=f"Knowledge base creation failed: {e!s}"
        )


@router.get("", response_model=KnowledgeBaseListResponse)
async def get_knowledge_bases(
    request: Request,
    limit: int = 50,
    offset: int = 0,
):
    """获取用户的知识库列表"""
    user_id = request.state.user_id
    logger.info(f"GET /knowledge-bases request from user: {user_id}")
    logger.info(f"Query parameters: limit={limit}, offset={offset}")
    mock_kb = KnowledgeBaseInfo(
        kb_id="kb_sample_001",
        name="示例知识库",
        description="这是一个示例知识库",
        user_id=user_id,
        document_count=0,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    return KnowledgeBaseListResponse(
        success=True,
        message="Knowledge bases retrieved successfully",
        knowledge_bases=[mock_kb],
        total_count=1,
        has_more=False,
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


@router.post("/{kb_id}/documents", response_model=ProcessDocumentResponse)
async def index_extracted_content_to_knowledge_base(
    request: Request,
    process_request: ProcessDocumentRequest,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
):
    """将已提取的内容索引到知识库"""
    try:
        user_id = request.state.user_id
        logger.info(f"POST /knowledge-bases/{kb_id}/documents from user: {user_id}")
        logger.info(f"Process request: {process_request.dict()}")

        # TODO: 1. Validate extraction_id exists and belongs to user.
        # TODO: 2. Validate kb_id exists and user has access.
        # TODO: 3. Call core knowledge_base module to perform chunking and indexing.

        # Mock response for now
        document_id = f"doc_{str(uuid.uuid4())[:8]}"
        processed_doc = ProcessedDocument(
            document_id=document_id,
            extraction_id=process_request.extraction_id,
            knowledge_base_id=kb_id,
            chunk_count=0,  # Placeholder
            indexing_status="processing",
            created_at=datetime.now().isoformat(),
        )

        return ProcessDocumentResponse(
            success=True,
            message="Document indexing started successfully",
            document=processed_doc,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing document for KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Document indexing failed: {e!s}")


@router.get("/{kb_id}/documents", response_model=List[ProcessedDocument])
async def get_knowledge_base_documents(
    request: Request,
    kb_id: str = FastAPIPath(..., description="知识库ID"),
    limit: int = 50,
    offset: int = 0,
):
    """获取知识库文档列表"""
    user_id = request.state.user_id
    logger.info(f"GET /knowledge-bases/{kb_id}/documents request from user: {user_id}")
    # TODO: Implement logic to get documents from a KB
    raise HTTPException(
        status_code=501,
        detail="Get knowledge base documents functionality not implemented yet",
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
