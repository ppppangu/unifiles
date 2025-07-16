"""
文件服务器
相关功能
1、指定用户id，接收二进制文件，保存到云端指定用户空间（没有的话会创建指定用户空间）。如果不指定用户名，则保存到公共空间，但是这个端口需要谨慎使用。
2、接收用户id，文件id，将云端文件进行处理（处理方式包括：不走ocr的向量化存储、走ocr的向量化存储（但是两者接口适配）、图谱处理）

启动命令：uv run uvicorn main:app --http httptools --host 0.0.0.0 --port 8087 --log-level debug --access-log
"""

# 导入web框架依赖
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 导入数据存储依赖
from minio import Minio

# 导入工具依赖
from loguru import logger
from pathlib import Path
from datetime import datetime
import uuid
import io
import httpx
from mineru_process import mineru_process
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from delete_file_module import delete_file_from_vcdb, delete_file_from_minio
from fix.fix_pg import fixpg_public_url_250613
# 导入图谱模块
from graph_module import produce_document_graph, get_documents_graph

# 导入配置
from src.tools import (
    read_config,
    read_pg_config,
    read_minio_config,
    mk_need_path,
    detect_content_type
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
        client_ip = request.client.host if request.client else None

    return client_ip



# 启动函数
async def start_up():
    """应用启动时执行的初始化操作"""
    # 创建必要的目录
    mk_need_path()
    logger.info("File server started successfully")
    # 检查chunk_schema.documents表的raw_file_public_url字段
    try:
        await fixpg_public_url_250613()
        logger.info("数据库修复检查完成")
    except Exception as e:
        logger.error(f"数据库修复检查失败，但服务器将继续启动: {str(e)}")
        # 继续启动服务器，不让数据库连接问题阻止服务启动

# 注册启动事件
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await start_up()
    yield
    # 关闭时执行（如果需要的话）

# 重新创建FastAPI应用实例，使用lifespan
app = FastAPI(
    title="File Server API",
    description="文件服务器API - 支持文件上传、处理和管理",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

document_file_types = [".doc",".docx",".ppt",".pptx",".xls",".xlsx",".odt",".ods",".odp",".txt",".rtf",".jpg",".jpeg",".png",".tiff",".tif",".bmp",".html",".htm",".md",".csv",".tsv",".xml"]

pdf_file_types = [".pdf"]

supported_file_types = document_file_types + pdf_file_types + [".py",".ipynb",".js",".json"]


# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok"}

# 获取支持的文件类型
@app.get("/get_supported_file_types")
async def get_supported_file_types():
    return {"status": "ok", "message": "Supported file types", "data": {"supported_file_types": supported_file_types}}


# 上传文件到云端，config桶里的bucket下的default目录，每个文件一个目录（目录名为生成的一个uuid），文件名即文件的原始文件名，不区分用户。返回值为公网url
@app.post("/upload_minio")
async def upload_minio(
    request: Request,
    upload_file: UploadFile = File(...),
    user_id: str = Form(default="default")
):
    try:
        logger.info("--> enter upload_minio")

        # 验证文件类型
        file_type = Path(upload_file.filename).suffix.lower()
        if file_type not in supported_file_types:
            logger.error(f"Unsupported file type: {file_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_type}"
            )

        client_ip = await get_client_ip(request)
        logger.info(f"Upload request received - user_id: {user_id} - client_ip: {client_ip}")

        # 获取文件信息
        filename = upload_file.filename
        if not filename:
            logger.error("No filename provided")
            raise HTTPException(
                status_code=400,
                detail="No filename provided"
            )

        # 计算文件大小（避免一次性读入内存）
        file_content = await upload_file.read()
        file_size = len(file_content)

        if file_size == 0:
            logger.error("Empty file provided")
            raise HTTPException(
                status_code=400,
                detail="Empty file provided"
            )

        logger.info(f"File info - name: {filename}, size: {file_size} bytes")

        # 生成UUID作为目录名
        file_uuid = str(uuid.uuid4())

        # 构建MinIO对象路径: default/{uuid}/{filename}
        object_path = f"{user_id}/default_file_space/{file_uuid}/{filename}"

        # 创建MinIO客户端
        minio_client = Minio(
            f"{minio_config['host']}:{int(minio_config['port'])}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False  # 根据配置调整
        )

        # 检查桶是否存在，不存在则创建
        bucket_name = minio_config["bucket_name"]
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")

        # 为上传设置合适的 Content-Type
        content_type = upload_file.content_type
        if not content_type or content_type == "application/octet-stream":
            content_type = detect_content_type(filename)

        # 上传文件到 MinIO（流式）
        minio_client.put_object(
            bucket_name,
            object_path,
            io.BytesIO(file_content),
            length=file_size,
            content_type=content_type,
            part_size=10 * 1024 * 1024  # 10MB 分片，避免一次性占用内存
        )

        logger.info(f"File uploaded successfully to MinIO: {object_path}")

        # 生成公网URL
        if minio_config.get("use_public_url", False) and minio_config.get("public_url_prefix"):
            public_url = f"{minio_config['public_url_prefix']}/{bucket_name}/{user_id}/default_file_space/{file_uuid}/{filename}"
        else:
            # 如果没有配置公网URL前缀，使用MinIO的默认URL
            public_url = f"http://{minio_config['host']}:{minio_config['port']}/{bucket_name}/{user_id}/default_file_space/{file_uuid}/{filename}"

        logger.info(f"Generated public URL: {public_url}")

        return {
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "file_id": file_uuid,
                "filename": filename,
                "object_path": object_path,
                "public_url": public_url,
                "file_size": file_size
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file to MinIO: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

# ---------------------- 公共辅助函数 ----------------------

def _fix_public_url(original_url: str) -> str:
    """如果 original_url 域名与配置的 public_url_prefix 不一致，则替换为配置前缀。"""
    try:
        public_prefix = config["server_components"]["minio"].get("public_url_prefix")
        if not public_prefix:
            return original_url
        if original_url.startswith(public_prefix):
            return original_url
        from urllib.parse import urlparse
        parsed = urlparse(original_url)
        fixed = f"{public_prefix}{parsed.path}"
        logger.info(f"_fix_public_url: 将 URL 从 {original_url} 修正为 {fixed}")
        return fixed
    except Exception as e:
        logger.warning(f"_fix_public_url 处理异常: {e}")
        return original_url

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
async def convert_document_to_pdf(file_url: str):
    try:
        # 验证URL格式
        if not file_url or not isinstance(file_url, str):
            logger.error(f"无效的文件URL: {file_url}")
            return None
            
        # 文件格式校验
        file_extension = file_url.split('.')[-1].lower() if '.' in file_url else ''
        logger.info(f"检测到文件扩展名: {file_extension}")
        
        if file_url.lower().endswith(".pdf"):
            logger.info(f"文件已经是PDF格式，无需转换: {file_url}")
            return _fix_public_url(file_url)
        
        # 检查是否为支持的文档格式
        is_supported = False
        for ext in document_file_types:
            if file_url.lower().endswith(ext):
                is_supported = True
                break
                
        if not is_supported:
            logger.error(f"不支持的文件类型: {file_extension}")
            return None
        
        # 调用转换服务
        logger.info(f"开始转换文件: {file_url}")
        convert_url = config["server_components"]["convert_format_server"][0]["url"] + "/convert"
        logger.info(f"转换服务URL: {convert_url}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(convert_url, data={"file_url": file_url})
            response.raise_for_status()
            result = response.json()
            
            if "converted_url" not in result or not result["converted_url"]:
                logger.error(f"转换服务返回无效结果: {result}")
                return None
                
            converted_url = result["converted_url"]
            logger.info(f"文件转换成功: {file_url} -> {converted_url}")
            converted_url = _fix_public_url(converted_url)
            return converted_url
    
    except httpx.HTTPStatusError as e:
        logger.error(f"转换服务HTTP错误: {e.response.status_code} - {e.response.reason_phrase}")
        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                logger.error(f"转换服务错误详情: {error_detail}")
            except:
                pass
        raise
    except httpx.RequestError as e:
        logger.error(f"转换服务请求错误: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"文件转换过程中发生未预期的错误: {str(e)}")
        return None

# 处理文件
@app.post("/process")
async def process(
    request: Request,
    user_id: str = Form(...),
    file_url: str = Form(...),
    knowledge_base_id: str = Form(default=None),
    mode: str = Form(default="simple")
):
    try:
        client_ip = await get_client_ip(request)
        logger.info(f"Process request received - user_id: {user_id} - client_ip: {client_ip} - file_url: {file_url} - knowledge_base_id: {knowledge_base_id} - mode: {mode}")

        # 验证file_url格式
        if not file_url.startswith(('http://', 'https://')):
            logger.error(f"无效的文件URL格式: {file_url}")
            raise HTTPException(status_code=400, detail="Invalid file URL format")

        # 设置默认值
        if not knowledge_base_id:
            knowledge_base_id = "df_" + user_id
            logger.info(f"使用默认knowledge_base_id: {knowledge_base_id}")

        if not mode:
            mode = "simple"
            logger.info(f"使用默认mode: {mode}")

        # 文件格式校验
        try:
            raw_file = file_url
            file_url = await convert_document_to_pdf(file_url)
            if not file_url:
                logger.error(f"不支持的文件类型或转换失败: {file_url}")
                raise HTTPException(status_code=400, detail="Unsupported file type or conversion failed")
        except Exception as e:
            logger.error(f"文件转换失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"File conversion failed: {str(e)}")

        # 处理文件
        try:
            if mode == "simple":
                return_url = await mineru_process(file_url, knowledge_base_id, mode, user_id,raw_file_url_to_return=raw_file)
                if not return_url:
                    logger.error("文件处理失败，未返回markdown_public_url")
                    raise HTTPException(status_code=500, detail="File processing failed")

                return {
                    "status": "ok",
                    "message": "File processed successfully",
                    "data": {
                        "user_id": user_id,
                        "knowledge_base_id": knowledge_base_id,
                        "mode": mode,
                        "file_url": raw_file,
                        "markdown_public_url": return_url["markdown_public_url"],
                        "pdf_file_public_url": return_url["pdf_file_public_url"],
                        "file_uuid": return_url["file_uuid"]
                    }
                }
            elif mode == "normal":
                file_uuid = ""
                return {
                    "status": "ok",
                    "message": "File processed successfully",
                    "data": {
                        "user_id": user_id,
                        "file_url": file_url,
                        "knowledge_base_id": knowledge_base_id,
                        "mode": mode,
                        "file_uuid": file_uuid,
                        "markdown_public_url": "",
                        "pdf_file_public_url": ""
                    }
                }
            else:
                logger.error(f"不支持的处理模式: {mode}")
                raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理文件时发生错误: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时发生未预期的错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# 删除文件
@app.post("/delete_file")
async def delete_file(
    request: Request,
    user_id: str = Form(...),
    file_id: str = Form(...),
    knowledge_base_id: str = Form(default=None)
):
    client_ip = await get_client_ip(request)
    logger.info(f"Delete file request received - user_id: {user_id} - client_ip: {client_ip} - file_id: {file_id} - knowledge_base_id: {knowledge_base_id}")

    if not knowledge_base_id:
        knowledge_base_id = "df_" + user_id

    # 删除文件
    await delete_file_from_vcdb(user_id, file_id, knowledge_base_id)
    await delete_file_from_minio(user_id, file_id, knowledge_base_id)
    return {"status": "ok", "message": "File deleted successfully"}

@app.post("/graph/knowledge_base")
async def graph_knowledge_base(
    request: Request,
    user_id: str = Form(...),
    knowledge_base_id: str = Form(...),
    mode: str = Form(...),
    level: str = Form(...)
):
    client_ip = await get_client_ip(request)
    logger.info(f"Knowledge base request received - user_id: {user_id} - client_ip: {client_ip} - knowledge_base_id: {knowledge_base_id}")

    if level == "document":
        if mode == "produce":
            result = await produce_document_graph(user_id, knowledge_base_id)
            return {"status": "ok", "message": "Document graph produced successfully", "data": result}
        elif mode == "get":
            result = await get_documents_graph(user_id, knowledge_base_id)
            return {"status": "ok", "message": "Document graph fetched successfully", "data": result}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
    elif level == "subject":
        if mode == "produce":
            return {"status": "ok", "message": "Knowledge base request received"}
        elif mode == "get":
            return {"status": "ok", "message": "Knowledge base request received"}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported level: {level}")



if __name__ == "__main__":
    import uvicorn
    # 提高单次请求体大小上限至 1GB
    uvicorn.run(app, host="0.0.0.0", port=8087)