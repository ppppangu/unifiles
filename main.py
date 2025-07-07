"""
文件服务器
相关功能
1、指定用户id，接收二进制文件，保存到云端指定用户空间（没有的话会创建指定用户空间）。如果不指定用户名，则保存到公共空间，但是这个端口需要谨慎使用。
2、接收用户id，文件id，将云端文件进行处理（处理方式包括：不走ocr的向量化存储、走ocr的向量化存储（但是两者接口适配）、图谱处理）
"""

# ---------------------------- Web 框架与中间件 ----------------------------
from fastapi import FastAPI, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------- 其他依赖 ----------------------------
import aiohttp
import aiofiles
import asyncpg
from minio import Minio
from loguru import logger
from pathlib import Path
from datetime import datetime
import uuid
import io
import time
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from mineru_process import mineru_process
from delete_file_module import delete_file_from_vcdb, delete_file_from_minio
from fix.fix_pg import fixpg_public_url_250613
from graph_module import produce_document_graph, get_documents_graph

from src.tools import (
    read_config,
    read_pg_config,
    read_minio_config,
    mk_need_path,
    detect_content_type,
)

# ---------------------------- 配置与日志 ----------------------------
config = read_config()
pg_config = read_pg_config()
minio_config = read_minio_config()

log_path = Path(__file__).parent / "logs"
logger.add(log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")

# ---------------------------- FastAPI 实例与 CORS ----------------------------
app = FastAPI(title="File Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ---------------------------- 工具函数 ----------------------------
async def get_client_ip(request: Request):
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None
    return client_ip

# ---------------------------- 启动事件 ----------------------------
async def start_up():
    """应用启动时执行的初始化操作"""
    mk_need_path()
    logger.info("File server started successfully")
    try:
        await fixpg_public_url_250613()
        logger.info("数据库修复检查完成")
    except Exception as e:
        logger.error(f"数据库修复检查失败，但服务器将继续启动: {str(e)}")

@app.on_event("startup")
async def on_startup():
    await start_up()

# ---------------------------- 文件类型常量 ----------------------------
document_file_types = [
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".txt",
    ".rtf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
    ".bmp",
    ".html",
    ".htm",
    ".md",
    ".csv",
    ".tsv",
    ".xml",
]

pdf_file_types = [".pdf"]

supported_file_types = document_file_types + pdf_file_types + [
    ".py",
    ".ipynb",
    ".js",
    ".json",
]

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
async def process(request: Request):
    try:
        # parase and validate
        form = await request.form()
        user_id = form.get("user_id")
        file_url = form.get("file_url")
        knowledge_base_id = form.get("knowledge_base_id")
        mode = form.get("mode")
        client_ip = await get_client_ip(request)
        logger.info(f"Process request received - user_id: {user_id} - client_ip: {client_ip} - file_url: {file_url} - knowledge_base_id: {knowledge_base_id} - mode: {mode}")

        # 基本参数验证
        if not user_id:
            logger.error("缺少必要参数: user_id")
            return JSONResponse({"status": "error", "message": "user_id is required"}, status_code=400)

        if not file_url:
            logger.error("缺少必要参数: file_url")
            return JSONResponse({"status": "error", "message": "file_url is required"}, status_code=400)

        # 验证file_url格式
        if not file_url.startswith(('http://', 'https://')):
            logger.error(f"无效的文件URL格式: {file_url}")
            return JSONResponse({"status": "error", "message": "Invalid file URL format"}, status_code=400)

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
                return JSONResponse({"status": "error", "message": "Unsupported file type or conversion failed"}, status_code=400)
        except Exception as e:
            logger.error(f"文件转换失败: {str(e)}")
            return JSONResponse({"status": "error", "message": f"File conversion failed: {str(e)}"}, status_code=500)

        # 处理文件
        try:
            if mode == "simple":
                return_url = await mineru_process(file_url, knowledge_base_id, mode, user_id,raw_file_url_to_return=raw_file)
                if not return_url:
                    logger.error("文件处理失败，未返回markdown_public_url")
                    return JSONResponse({"status": "error", "message": "File processing failed"}, status_code=500)
                
                return JSONResponse({
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
                })
            elif mode == "normal":
                file_uuid = ""
                return JSONResponse({
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
                })
            else:
                logger.error(f"不支持的处理模式: {mode}")
                return JSONResponse({"status": "error", "message": f"Unsupported mode: {mode}"}, status_code=400)
        except Exception as e:
            logger.error(f"处理文件时发生错误: {str(e)}")
            return JSONResponse({"status": "error", "message": f"Error processing file: {str(e)}"}, status_code=500)
    
    except Exception as e:
        logger.error(f"处理请求时发生未预期的错误: {str(e)}")
        return JSONResponse({"status": "error", "message": f"Unexpected error: {str(e)}"}, status_code=500)

# 删除文件
@app.post("/delete_file")
async def delete_file(request: Request):
    form = await request.form()
    user_id = form.get("user_id")
    file_id = form.get("file_id")
    knowledge_base_id = form.get("knowledge_base_id")
    client_ip = await get_client_ip(request)
    logger.info(f"Delete file request received - user_id: {user_id} - client_ip: {client_ip} - file_id: {file_id} - knowledge_base_id: {knowledge_base_id}")
    if not user_id:
        return JSONResponse({"status": "error", "message": "user_id is required"}, status_code=400)
    if not file_id:
        return JSONResponse({"status": "error", "message": "file_id is required"}, status_code=400)
    if not knowledge_base_id:
        knowledge_base_id = "df_" + user_id
    # 删除文件
    await delete_file_from_vcdb(user_id, file_id, knowledge_base_id)
    await delete_file_from_minio(user_id, file_id, knowledge_base_id)
    return JSONResponse({"status": "ok", "message": "File deleted successfully"})

@app.post("/graph/knowledge_base")
async def graph_knowledge_base(request: Request):
    form = await request.form()
    user_id = form.get("user_id")
    knowledge_base_id = form.get("knowledge_base_id")
    mode = form.get("mode")
    level = form.get("level")
    client_ip = await get_client_ip(request)
    logger.info(f"Knowledge base request received - user_id: {user_id} - client_ip: {client_ip} - knowledge_base_id: {knowledge_base_id}")
    if not user_id:
        return JSONResponse({"status": "error", "message": "user_id is required"}, status_code=400)
    if not knowledge_base_id:
        return JSONResponse({"status": "error", "message": "knowledge_base_id is required"}, status_code=400)
    if not mode:
        return JSONResponse({"status": "error", "message": "mode is required"}, status_code=400)
    if not level:
        return JSONResponse({"status": "error", "message": "level is required"}, status_code=400)
    if level == "document":
        if mode == "produce":
            result = await produce_document_graph(user_id, knowledge_base_id)
            return JSONResponse({"status": "ok", "message": "Document graph produced successfully", "data": result})
        elif mode == "get":
            result = await get_documents_graph(user_id, knowledge_base_id)
            return JSONResponse({"status": "ok", "message": "Document graph fetched successfully", "data": result})
        else:
            return JSONResponse({"status": "error", "message": "Unsupported mode: {mode}"}, status_code=400)
    elif level == "subject":
        if mode == "produce":
            return JSONResponse({"status": "ok", "message": "Knowledge base request received"})
        elif mode == "get":
            return JSONResponse({"status": "ok", "message": "Knowledge base request received"})
        else:
            return JSONResponse({"status": "error", "message": "Unsupported mode: {mode}"}, status_code=400)
    else:
        return JSONResponse({"status": "error", "message": "Unsupported level: {level}"}, status_code=400)


# 需要确保中间件能下载跨域文件
# middleware = [
#     Middleware(CORSMiddleware,         
#                allow_origins=["*"], 
#                allow_credentials=True, 
#                allow_methods=["*"], 
#                allow_headers=["*"],
#                expose_headers=["*"]
#                )
# ]

# app = Starlette(
#     middleware=middleware,
#     routes=[
#         Route("/health", health,methods=["GET"]),
#         Route("/get_supported_file_types", get_supported_file_types,methods=["GET"]),
#         Route("/upload_minio", upload_minio,methods=["POST"]),
#         Route("/process", process,methods=["POST"]),
#         Route("/delete_file", delete_file,methods=["POST"]),
#         Route("/graph/knowledge_base", graph_knowledge_base,methods=["POST"])
#     ],
#     on_startup=[start_up]
# )

if __name__ == "__main__":
    import uvicorn
    # 提高单次请求体大小上限至 1GB
    uvicorn.run(app, host="0.0.0.0", port=8087)