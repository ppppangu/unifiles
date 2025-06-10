"""
文件服务器
相关功能
1、指定用户id，接收二进制文件，保存到云端指定用户空间（没有的话会创建指定用户空间）。如果不指定用户名，则保存到公共空间，但是这个端口需要谨慎使用。
2、接收用户id，文件id，将云端文件进行处理（处理方式包括：不走ocr的向量化存储、走ocr的向量化存储（但是两者接口适配）、图谱处理）
"""

# 导入web框架依赖
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# 导入异步依赖
import aiohttp
import aiofiles

# 导入数据库依赖
import asyncpg

# 导入数据存储依赖
from minio import Minio

# 导入工具依赖
from loguru import logger
from pathlib import Path
from datetime import datetime
import uuid
import io
import time

# 导入配置
from src.tools import (
    read_config,
    read_pg_config,
    read_minio_config,
    mk_need_path
)

# 读取相关配置
config = read_config()
pg_config = read_pg_config()
minio_config = read_minio_config()

# 日志配置
log_path = Path(__file__).parent / "logs"
logger.add(log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")

async def get_client_ip(request: Request):
    # 尝试从常见的HTTP头获取真实IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For可能包含多个IP，第一个通常是客户端真实IP
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        # 如果没有代理信息，则使用直接连接的客户端IP
        client_ip = request.client[0] if request.client else None
    
    return client_ip

# 启动函数
async def start_up():
    """应用启动时执行的初始化操作"""
    # 创建必要的目录
    mk_need_path()
    logger.info("File server started successfully")

# 健康检查
async def health(request: Request):
    return JSONResponse({"status": "ok"})

# 上传文件到云端，config桶里的bucket下的default目录，每个文件一个目录（目录名为生成的一个uuid），文件名即文件的原始文件名，不区分用户。返回值为公网url
async def upload_minio(request: Request):
    try:
        # 解析和验证表单数据
        form = await request.form()

        # 解析参数
        user_id = form.get("user_id")
        if not user_id:
            user_id = "default"
        upload_file = form.get("upload_file")
        client_ip = await get_client_ip(request)
        logger.info(f"Upload request received - user_id: {user_id} - client_ip: {client_ip}")

        # 验证必需参数
        if not upload_file:
            logger.error("No file provided in upload request")
            return JSONResponse(
                {"status": "error", "message": "No file provided"},
                status_code=400
            )

        # 获取文件信息
        filename = upload_file.filename
        if not filename:
            logger.error("No filename provided")
            return JSONResponse(
                {"status": "error", "message": "No filename provided"},
                status_code=400
            )

        # 读取文件内容
        file_content = await upload_file.read()
        if not file_content:
            logger.error("Empty file provided")
            return JSONResponse(
                {"status": "error", "message": "Empty file provided"},
                status_code=400
            )

        logger.info(f"File info - name: {filename}, size: {len(file_content)} bytes")

        # 生成UUID作为目录名
        file_uuid = str(uuid.uuid4())

        # 构建MinIO对象路径: default/{uuid}/{filename}
        object_path = f"{user_id}/default_file_space/{file_uuid}/{filename}"

        # 创建MinIO客户端
        minio_client = Minio(
            f"{minio_config['host']}:{minio_config['port']}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False  # 根据配置调整
        )

        # 检查桶是否存在，不存在则创建
        bucket_name = minio_config["bucket_name"]
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")

        # 上传文件到MinIO
        file_stream = io.BytesIO(file_content)
        minio_client.put_object(
            bucket_name,
            object_path,
            file_stream,
            length=len(file_content),
            content_type=upload_file.content_type or "application/octet-stream"
        )

        logger.info(f"File uploaded successfully to MinIO: {object_path}")

        # 生成公网URL
        if minio_config.get("use_public_url", False) and minio_config.get("public_url_prefix"):
            public_url = f"{minio_config['public_url_prefix']}/{bucket_name}/{user_id}/default_file_space/{file_uuid}/{filename}"
        else:
            # 如果没有配置公网URL前缀，使用MinIO的默认URL
            public_url = f"http://{minio_config['host']}:{minio_config['port']}/{bucket_name}/{user_id}/default_file_space/{file_uuid}/{filename}"

        logger.info(f"Generated public URL: {public_url}")

        return JSONResponse({
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "file_id": file_uuid,
                "filename": filename,
                "object_path": object_path,
                "public_url": public_url,
                "file_size": len(file_content)
            }
        })

    except Exception as e:
        logger.error(f"Error uploading file to MinIO: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": f"Upload failed: {str(e)}"},
            status_code=500
        )

# 处理文件
async def process(request: Request):
    # parase and validate
    form = await request.form()
    user_id = form.get("user_id")
    file_url = form.get("file_url")
    knowledge_base_id = form.get("knowledge_base_id")
    mode = form.get("mode")
    client_ip = await get_client_ip(request)
    logger.info(f"Process request received - user_id: {user_id} - client_ip: {client_ip} - file_url: {file_url} - knowledge_base_id: {knowledge_base_id} - mode: {mode}")

    if not user_id:
        return JSONResponse({"status": "error", "message": "user_id is required"}, status_code=400)

    if not file_url:
        return JSONResponse({"status": "error", "message": "file_url is required"}, status_code=400)

    if not knowledge_base_id:
        knowledge_base_id = "df_" + user_id

    if not mode:
        mode = "simple"

    time.sleep(10)
    markdown_public_url = "https://www.example_markdown_url.com"

    return JSONResponse({"status": "ok", "message": "File processed successfully", "data": {"user_id": user_id, "file_url": file_url, "knowledge_base_id": knowledge_base_id, "mode": mode, "markdown_public_url": markdown_public_url}})

middleware = [
    Middleware(CORSMiddleware, 
               allow_origins=["*"], 
               allow_credentials=True, 
               allow_methods=["*"], 
               allow_headers=["*"],
               expose_headers=["*"]
               )
]

app = Starlette(
    middleware=middleware,
    routes=[
        Route("/health", health,methods=["GET"]),
        Route("/upload_minio", upload_minio,methods=["POST"]),
        Route("/process", process,methods=["POST"]),
    ],
    on_startup=[start_up]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)