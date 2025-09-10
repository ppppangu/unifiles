"""
V1 API 文档处理集成
展示如何使用新的核心模块来替代legacy的处理逻辑
"""

from fastapi import HTTPException
from loguru import logger
from typing import Dict, Any

from server.core.services import DocumentProcessingService, get_document_processor


class V1DocumentProcessor:
    """V1 API 文档处理器"""
    
    def __init__(self):
        self.processor = get_document_processor()
    
    async def process_document_url(self, file_url: str, user_id: str, 
                                 knowledge_base_id: str, mode: str = "simple") -> Dict[str, Any]:
        """
        处理文档URL（替代legacy/main.py中的mineru_process函数）
        
        Args:
            file_url: 文件URL
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            mode: 处理模式
            
        Returns:
            处理结果
        """
        try:
            logger.info(f"V1 API processing document: {file_url}")
            logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            
            # 使用新的核心模块处理文档
            result = await self.processor.process_file_from_url(
                file_url=file_url,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                mode=mode,
                raw_file_url_to_return=file_url
            )
            
            if result is None:
                raise HTTPException(status_code=500, detail="Document processing failed")
            
            logger.info(f"V1 API document processing completed successfully")
            return {
                "success": True,
                "message": "File processed successfully",
                "data": {
                    "user_id": user_id,
                    "knowledge_base_id": knowledge_base_id,
                    "mode": mode,
                    "file_url": file_url,
                    "markdown_public_url": result["markdown_public_url"],
                    "pdf_file_public_url": result["pdf_file_public_url"],
                    "file_uuid": result["file_uuid"]
                }
            }
            
        except Exception as e:
            logger.error(f"V1 API document processing failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
    async def process_uploaded_file(self, filename: str, file_content: bytes,
                                  user_id: str, knowledge_base_id: str, 
                                  mode: str = "simple") -> Dict[str, Any]:
        """
        处理上传的文件
        
        Args:
            filename: 文件名
            file_content: 文件内容
            user_id: 用户ID
            knowledge_base_id: 知识库ID
            mode: 处理模式
            
        Returns:
            处理结果
        """
        try:
            logger.info(f"V1 API processing uploaded file: {filename}")
            logger.info(f"User: {user_id}, KB: {knowledge_base_id}, Mode: {mode}")
            
            # 使用新的核心模块处理上传文件
            result = await self.processor.process_file_from_upload(
                filename=filename,
                file_content=file_content,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                mode=mode
            )
            
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))
            
            logger.info(f"V1 API uploaded file processing completed successfully")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"V1 API uploaded file processing failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing uploaded file: {str(e)}")
    
    def get_processor_info(self) -> Dict[str, Any]:
        """获取处理器信息"""
        return self.processor.get_service_info()


# 默认处理器实例
_v1_processor: V1DocumentProcessor = None


def get_v1_processor() -> V1DocumentProcessor:
    """获取V1处理器实例（单例）"""
    global _v1_processor
    if _v1_processor is None:
        _v1_processor = V1DocumentProcessor()
    return _v1_processor