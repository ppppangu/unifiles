"""
文件服务器
相关功能
1、指定用户id，接收二进制文件，保存到云端指定用户空间（没有的话会创建指定用户空间）。如果不指定用户名，则保存到公共空间，但是这个端口需要谨慎使用。
2、接收用户id，文件id，将云端文件进行处理（处理方式包括：不走ocr的向量化存储、走ocr的向量化存储（但是两者接口适配）、图谱处理）

启动命令：uv run uvicorn main:app --http httptools --host 0.0.0.0 --port 8087 --log-level debug --access-log
"""

# Web框架和异步生命周期依赖
# 提供FastAPI应用的上下文管理和异步启动/关闭钩子
# 支持上下文管理和生命周期事件处理

# 导入Web框架依赖
# 注册应用启动和关闭事件，实现资源初始化和清理
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from delete_file_module import delete_file_from_minio, delete_file_from_vcdb
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fix.fix_pg import fixpg_public_url_250613

# 导入图谱模块
from graph_module import get_documents_graph, produce_document_graph

# 导入工具依赖
from loguru import logger
from mineru_process import mineru_process

# 导入配置
from src.tools import mk_need_path, read_config, read_minio_config, read_pg_config
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 导入文件上传工具
from utils import (
    DOCUMENT_FILE_TYPES,
    SUPPORTED_FILE_TYPES,
    get_supported_file_types,
    upload_file_to_minio,
)

# 读取相关配置
config = read_config()
pg_config = read_pg_config()
minio_config = read_minio_config()

# 日志配置
log_path = Path(__file__).parent / "logs"
logger.add(log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")


async def get_client_ip(request: Request):
    """从请求中提取客户端真实IP地址

    通过检查X-Forwarded-For和直接客户端连接来获取IP
    适用于代理和直接连接两种场景

    Args:
        request (Request): FastAPI请求对象

    Returns:
        str: 客户端IP地址，如果无法获取则返回None
    """
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
    """应用启动时的初始化操作

    负责执行以下关键启动任务：
    1. 创建必要的目录结构
    2. 检查并修复数据库相关问题
    3. 记录启动日志

    主要目的：
    - 确保应用启动前环境已准备就绪
    - 执行必要的系统初始化操作
    - 处理可能的数据库兼容性和迁移问题

    处理策略：
    - 如果数据库修复失败，记录错误但不阻止服务启动
    - 优先保证服务可用性
    """
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI应用的生命周期管理器

    这个上下文管理器负责处理应用的生命周期，包括：

    1. 应用启动流程：
       - 执行初始化操作（调用start_up()）
       - 创建必要的资源和连接
       - 处理可能出现的启动时错误

    2. 应用关闭流程：
       - 关闭所有打开的资源和连接
       - 执行清理操作
       - 保证应用以可控的方式退出

    实现使用了 Python 的异步上下文管理器，确保资源的正确初始化和清理
    """
    # 启动时执行初始化操作
    await start_up()
    yield
    # 关闭时执行清理操作（如果需要的话）


# 重新创建FastAPI应用实例，使用lifespan
app = FastAPI(
    title="File Server API",
    description="文件服务器API - 支持文件上传、处理和管理",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 使用工具类中定义的支持文件类型
supported_file_types = SUPPORTED_FILE_TYPES


# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok"}


# 获取支持的文件类型
@app.get("/get_supported_file_types")
async def get_supported_file_types_endpoint():
    file_types = get_supported_file_types()
    return {
        "status": "ok",
        "message": "Supported file types",
        "data": {"supported_file_types": file_types["all_supported"]},
    }


# 上传文件到云端，config桶里的bucket下的default目录，每个文件一个目录（目录名为生成的一个uuid），文件名即文件的原始文件名，不区分用户。返回值为公网url
@app.post("/upload_minio")
async def upload_minio_endpoint(
    request: Request,
    upload_file: UploadFile = File(...),
    user_id: str = Form(default="default"),
):
    try:
        logger.info("--> enter upload_minio")

        client_ip = await get_client_ip(request)
        logger.info(
            f"Upload request received - user_id: {user_id} - client_ip: {client_ip}"
        )

        # 使用工具函数上传文件
        upload_result = await upload_file_to_minio(upload_file, user_id)

        logger.info("File uploaded successfully via utils")

        return {
            "status": "success",
            "message": "File uploaded successfully",
            "data": upload_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file to MinIO: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ---------------------- 公共辅助函数 ----------------------


def _fix_public_url(original_url: str) -> str:
    """修正公共访问地址，确保一致性和可访问性

    此函数用于解决跨域资源和代理执行时可能出现的URL一致性问题

    主要功能：
    1. 检查原始 URL 的域名是否与配置的 public_url_prefix 一致
    2. 如果不一致，则使用配置中的前缀替换
    3. 保留原始 URL 的路径部分

    错误处理：
    - 如果配置中没有 public_url_prefix，则保留原始 URL
    - 如果出现异常，记录警告并返回原始 URL

    Args:
        original_url (str): 原始URL

    Returns:
        str: 修正后的URL
    """
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
    stop=stop_after_attempt(3),  # 最大重试3次
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 指数退避重试策略
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),  # 仅在网络和HTTP错误时重试
)
async def convert_document_to_pdf(file_url: str):
    """文档格式转换函数，将各种文档格式转换为PDF

    详细功能：
    1. 验证文件URL的有效性
    2. 检查文件类型并判断是否需要转换
    3. 调用转换服务进行格式转换
    4. 执行必要的错误处理和重试机制

    重试机制：
    - 允许最多3次重试
    - 使用指数退陥重试策略，随着重试次数增加等待时间
    - 仅在网络和HTTP错误时重试

    处理流程：
    1. 验证文件URL格式
    2. 检查文件是否已是PDF
    3. 检查文件是否为受支持的文档类型
    4. 调用转换服务
    5. 修正转换后的URL

    Args:
        file_url (str): 转换前的文件URL

    Returns:
        str: 转换后的PDF文件URL，转换失败则返回None

    Raises:
        HTTPException: 转换过程中发生的HTTP错误
        RequestException: 网络请求错误
    """
    try:
        # 验证URL格式
        if not file_url or not isinstance(file_url, str):
            logger.error(f"无效的文件URL: {file_url}")
            return None

        # 文件格式校验
        file_extension = file_url.split(".")[-1].lower() if "." in file_url else ""
        logger.info(f"检测到文件扩展名: {file_extension}")

        if file_url.lower().endswith(".pdf"):
            logger.info(f"文件已经是PDF格式，无需转换: {file_url}")
            return _fix_public_url(file_url)

        # 检查是否为支持的文档格式
        is_supported = False
        for ext in DOCUMENT_FILE_TYPES:
            if file_url.lower().endswith(ext):
                is_supported = True
                break

        if not is_supported:
            logger.error(f"不支持的文件类型: {file_extension}")
            return None

        # 调用转换服务
        logger.info(f"开始转换文件: {file_url}")
        convert_url = (
            config["server_components"]["convert_format_server"][0]["url"] + "/convert"
        )
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
        logger.error(
            f"转换服务HTTP错误: {e.response.status_code} - {e.response.reason_phrase}"
        )
        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                logger.error(f"转换服务错误详情: {error_detail}")
            except Exception:
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
    mode: str = Form(default="simple"),
):
    """文档处理端点，提供多种文档处理模式的综合服务

    主要功能：
    1. 文档格式验证和转换
    2. 支持多种处理模式：
       - simple模式：基础向量化处理
       - normal模式：基础文件处理

    详细处理步骤：
    1. 获取客户端IP并记录请求日志
    2. 验证文件URL格式的有效性
    3. 设置默认的knowledge_base_id和处理模式
    4. 尝试将文件转换为PDF格式
    5. 根据指定模式处理文件
       - simple模式：调用MinErU进行文档处理和向量化
       - normal模式：基础文件处理

    处理模式说明：
    - simple模式：
      a. 文档转PDF
      b. 调用MinErU处理服务
      c. 生成Markdown和向量化表示
    - normal模式：仅基础处理，不生成Markdown

    错误处理：
    - 详细记录每个阶段的错误日志
    - 使用HTTPException返回具体错误信息
    - 确保系统稳定性和可观测性

    Args:
        request (Request): FastAPI请求对象
        user_id (str): 用户ID
        file_url (str): 待处理文件的URL
        knowledge_base_id (str, optional): 指定的文档库ID，默认为用户默认库
        mode (str, optional): 处理模式，默认为simple

    Returns:
        dict: 包含处理结果的响应对象，返回文件处理的详细信息

    Raises:
        HTTPException: 文件处理过程中的各种错误，如URL无效、文件转换失败等
    """
    try:
        client_ip = await get_client_ip(request)
        logger.info(
            f"Process request received - user_id: {user_id} - client_ip: {client_ip} - file_url: {file_url} - knowledge_base_id: {knowledge_base_id} - mode: {mode}"
        )

        # 验证file_url格式
        if not file_url.startswith(("http://", "https://")):
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
                raise HTTPException(
                    status_code=400, detail="Unsupported file type or conversion failed"
                )
        except Exception as e:
            logger.error(f"文件转换失败: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"File conversion failed: {str(e)}"
            )

        # 处理文件
        try:
            if mode == "simple":
                return_url = await mineru_process(
                    file_url,
                    knowledge_base_id,
                    mode,
                    user_id,
                    raw_file_url_to_return=raw_file,
                )
                if not return_url:
                    logger.error("文件处理失败，未返回markdown_public_url")
                    raise HTTPException(
                        status_code=500, detail="File processing failed"
                    )

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
                        "file_uuid": return_url["file_uuid"],
                    },
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
                        "pdf_file_public_url": "",
                    },
                }
            else:
                logger.error(f"不支持的处理模式: {mode}")
                raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理文件时发生错误: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error processing file: {str(e)}"
            )

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
    knowledge_base_id: str = Form(default=None),
):
    """文档删除端点，从向量数据库和对象存储中删除文件

    主要功能：
    1. 从向量数据库（Vector DB）中删除文档向量表示
    2. 从对象存储服务（MinIO）中删除对应的文件

    注意事项：
    - 如果未指定knowledge_base_id，将使用用户默认文档库
    - 删除操作是并行执行，以提高效率

    处理步骤：
    1. 获取客户端IP
    2. 记录删除操作日志
    3. 将不指定knowledge_base_id的情况设置默认值
    4. 分别从向量数据库和对象存储删除文件

    Args:
        request (Request): FastAPI请求对象
        user_id (str): 用户ID
        file_id (str): 待删除文件的ID
        knowledge_base_id (str, optional): 文档库ID，默认使用用户默认文档库

    Returns:
        dict: 删除操作的状态响应

    Raises:
        HTTPException: 如果删除操作出现错误
    """
    client_ip = await get_client_ip(request)
    logger.info(
        f"Delete file request received - user_id: {user_id} - client_ip: {client_ip} - file_id: {file_id} - knowledge_base_id: {knowledge_base_id}"
    )

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
    level: str = Form(...),
):
    """知识图谱管理端点，提供文档和主题级图谱的生成与查询

    主要功能：
    1. 对不同层级的知识图谱进行管理
       - 文档级（document level）
       - 主题级（subject level）
    2. 支持图谱的生成和查询操作

    层级说明：
    - document层：以单个文档为单位的图谱
    - subject层：以主题为单位的图谱，目前实现尚未完成

    操作模式：
    - produce：生成图谱
    - get：获取已生成的图谱

    处理步骤：
    1. 获取客户端IP
    2. 记录请求日志
    3. 根据不同的层级和模式执行相应操作

    Args:
        request (Request): FastAPI请求对象
        user_id (str): 用户ID
        knowledge_base_id (str): 知识库ID
        mode (str): 操作模式（produce/get）
        level (str): 图谱层级（document/subject）

    Returns:
        dict: 图谱操作的状态响应，包含生成或查询的图谱数据

    Raises:
        HTTPException: 如果提供了不支持的mode或level
    """
    client_ip = await get_client_ip(request)
    logger.info(
        f"Knowledge base request received - user_id: {user_id} - client_ip: {client_ip} - knowledge_base_id: {knowledge_base_id}"
    )

    if level == "document":
        if mode == "produce":
            result = await produce_document_graph(user_id, knowledge_base_id)
            return {
                "status": "ok",
                "message": "Document graph produced successfully",
                "data": result,
            }
        elif mode == "get":
            result = await get_documents_graph(user_id, knowledge_base_id)
            return {
                "status": "ok",
                "message": "Document graph fetched successfully",
                "data": result,
            }
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
