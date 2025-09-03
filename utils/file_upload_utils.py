"""
文件上传和存储工具类
提供可复用的文件上传、验证和MinIO存储功能
"""

from fastapi import UploadFile, HTTPException
from minio import Minio
from pathlib import Path
from loguru import logger
from typing import Dict, Optional, Tuple
import uuid
import io
from src.tools import read_minio_config, detect_content_type


# 支持的文件类型定义
DOCUMENT_FILE_TYPES = [
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", 
    ".odt", ".ods", ".odp", ".txt", ".rtf", ".jpg", 
    ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".html", 
    ".htm", ".md", ".csv", ".tsv", ".xml"
]

PDF_FILE_TYPES = [".pdf"]

SUPPORTED_FILE_TYPES = DOCUMENT_FILE_TYPES + PDF_FILE_TYPES + [".py", ".ipynb", ".js", ".json"]


def validate_file_type(filename: str) -> bool:
    """
    验证文件类型是否受支持
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否支持该文件类型
    """
    if not filename:
        return False
        
    file_type = Path(filename).suffix.lower()
    return file_type in SUPPORTED_FILE_TYPES


def validate_file_content(file_content: bytes, filename: str) -> Tuple[bool, str]:
    """
    验证文件内容
    
    Args:
        file_content: 文件内容字节
        filename: 文件名
        
    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if not filename:
        return False, "No filename provided"
        
    if not validate_file_type(filename):
        file_type = Path(filename).suffix.lower()
        return False, f"Unsupported file type: {file_type}"
        
    if len(file_content) == 0:
        return False, "Empty file provided"
        
    return True, ""


def create_minio_client() -> Minio:
    """
    创建MinIO客户端
    
    Returns:
        Minio: MinIO客户端实例
    """
    minio_config = read_minio_config()
    
    return Minio(
        f"{minio_config['host']}:{int(minio_config['port'])}",
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False
    )


def ensure_bucket_exists(minio_client: Minio, bucket_name: str) -> None:
    """
    确保桶存在，不存在则创建
    
    Args:
        minio_client: MinIO客户端
        bucket_name: 桶名称
    """
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)
        logger.info(f"Created bucket: {bucket_name}")


def generate_object_path(user_id: str, filename: str, file_uuid: Optional[str] = None) -> Tuple[str, str]:
    """
    生成MinIO对象路径
    
    Args:
        user_id: 用户ID
        filename: 文件名
        file_uuid: 文件UUID，如果不提供则自动生成
        
    Returns:
        Tuple[str, str]: (对象路径, 文件UUID)
    """
    if not file_uuid:
        file_uuid = str(uuid.uuid4())
        
    object_path = f"{user_id}/default_file_space/{file_uuid}/{filename}"
    return object_path, file_uuid


def generate_public_url(bucket_name: str, object_path: str) -> str:
    """
    生成文件的公网URL
    
    Args:
        bucket_name: 桶名称
        object_path: 对象路径
        
    Returns:
        str: 公网URL
    """
    minio_config = read_minio_config()
    
    if minio_config.get("use_public_url", False) and minio_config.get("public_url_prefix"):
        public_url = f"{minio_config['public_url_prefix']}/{bucket_name}/{object_path}"
    else:
        public_url = f"http://{minio_config['host']}:{minio_config['port']}/{bucket_name}/{object_path}"
        
    return public_url


async def upload_file_to_minio(
    upload_file: UploadFile,
    user_id: str = "default",
    file_uuid: Optional[str] = None
) -> Dict[str, any]:
    """
    上传文件到MinIO存储
    
    Args:
        upload_file: FastAPI上传文件对象
        user_id: 用户ID，默认为"default"
        file_uuid: 文件UUID，如果不提供则自动生成
        
    Returns:
        Dict: 包含上传结果的字典
        
    Raises:
        HTTPException: 上传失败时抛出异常
    """
    try:
        # 获取文件信息
        filename = upload_file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        # 读取文件内容
        file_content = await upload_file.read()
        file_size = len(file_content)
        
        # 验证文件
        is_valid, error_msg = validate_file_content(file_content, filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
            
        logger.info(f"File info - name: {filename}, size: {file_size} bytes")
        
        # 生成对象路径
        object_path, generated_uuid = generate_object_path(user_id, filename, file_uuid)
        
        # 创建MinIO客户端
        minio_client = create_minio_client()
        minio_config = read_minio_config()
        bucket_name = minio_config["bucket_name"]
        
        # 确保桶存在
        ensure_bucket_exists(minio_client, bucket_name)
        
        # 设置Content-Type
        content_type = upload_file.content_type
        if not content_type or content_type == "application/octet-stream":
            content_type = detect_content_type(filename)
            
        # 上传文件
        minio_client.put_object(
            bucket_name,
            object_path,
            io.BytesIO(file_content),
            length=file_size,
            content_type=content_type,
            part_size=10 * 1024 * 1024  # 10MB 分片
        )
        
        logger.info(f"File uploaded successfully to MinIO: {object_path}")
        
        # 生成公网URL
        public_url = generate_public_url(bucket_name, object_path)
        logger.info(f"Generated public URL: {public_url}")
        
        return {
            "file_id": generated_uuid,
            "filename": filename,
            "object_path": object_path,
            "public_url": public_url,
            "file_size": file_size,
            "content_type": content_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file to MinIO: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def upload_file_with_validation(
    upload_file: UploadFile,
    user_id: str = "default",
    allowed_types: Optional[list] = None
) -> Dict[str, any]:
    """
    带额外验证的文件上传函数
    
    Args:
        upload_file: FastAPI上传文件对象
        user_id: 用户ID
        allowed_types: 允许的文件类型列表，None表示使用默认支持的类型
        
    Returns:
        Dict: 上传结果
        
    Raises:
        HTTPException: 验证或上传失败时抛出异常
    """
    # 如果指定了允许的文件类型，进行额外验证
    if allowed_types is not None:
        filename = upload_file.filename
        if filename:
            file_type = Path(filename).suffix.lower()
            if file_type not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type {file_type} not allowed. Allowed types: {allowed_types}"
                )
    
    return await upload_file_to_minio(upload_file, user_id)


def get_supported_file_types() -> Dict[str, list]:
    """
    获取支持的文件类型
    
    Returns:
        Dict: 包含各类文件类型的字典
    """
    return {
        "document_types": DOCUMENT_FILE_TYPES,
        "pdf_types": PDF_FILE_TYPES,
        "all_supported": SUPPORTED_FILE_TYPES
    }