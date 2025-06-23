# 导入必要库
import os
import pathlib
import boto3
import asyncio
import aiohttp
import time
from pydantic import BaseModel
from loguru import logger
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从环境变量中获取 s3 云存储的配置，用于上传文件到 s3 云存储
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_REGION = os.getenv("S3_REGION")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")

# 转换后的pdf在 S3 过期时间，单位为秒, 为0表示不设置过期时间
PDF_EXPIRE_TIME = int(os.getenv("PDF_EXPIRE_TIME", 0))
# 返回的下载地址，如果为空则返回S3ENDPOINTURL/BUCKETNAME/convert_file2pdf_server/文件名，不为空返回响应里为这里的下载地址开头，用于进行了端口映射后的情况
DOWNLOAD_URL_PREFIX = os.getenv("DOWNLOAD_URL_PREFIX", "")

supported_file_types = [
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".odt", ".ods", ".odp", ".txt", ".rtf",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp",
    ".html", ".htm", ".md", ".csv", ".tsv", ".xml"
]

# 编写初始化函数和关闭函数
async def on_startup():
    # 初始化 s3 客户端，测试连通性
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT_URL)
    try:
        s3_client.list_buckets()
        logger.info(f"S3 连接成功: {S3_ENDPOINT_URL}")
    except Exception as e:
        logger.error(f"S3 server is unusable: {e}")
        logger.warning("将继续启动服务，但S3相关功能可能无法正常工作")
        # 不再抛出异常，允许服务继续启动
    finally:
        try:
            s3_client.close()
        except Exception as e:
            logger.error(f"Failed to close s3 client: {e}")
            
    # 设置 日志文件 位置，每次启动自动生成一个log文件
    log_file = pathlib.Path(__file__).parent / "logs" / f"log_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, rotation="100 MB", retention="1000 days")
    logger.info(f"server start up, time: {time.strftime('%Y-%m-%d %H:%M:%S')}, s3 url is: {S3_ENDPOINT_URL}, log file is at: {log_file}")

async def on_shutdown():
    logger.info(f"server shut down, time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

# 健康检查接口
async def health(request: Request):
    return JSONResponse({"status": "ok"}, status_code=200)

# 获取支持的文件类型接口
async def get_supported_file_types(request:Request):
    return JSONResponse({"supported_file_types": supported_file_types}, status_code=200)

class ConvertRequest(BaseModel):
    file_url: str

# 转换文件格式接口
async def convert(request: Request):
    # 获取客户端ip地址和表单数据
    client_ip = request.client.host
    form_data = await request.form()
    logger.info(f"client ip is : {client_ip}, time: {time.strftime('%Y-%m-%d %H:%M:%S')}, form data is: {form_data}")

    # 获取文件的s3 url地址，用于下载文件
    file_url = form_data.get("file_url")
    if not file_url:
        return JSONResponse({"error": "file_url is required"}, status_code=400)

    # 清理URL，移除多余的引号和反斜杠
    file_url = file_url.strip('"\'\\[]')

    # 提取文件扩展名并清理
    file_extension = file_url.split('.')[-1].strip('"\'\\[]')

    if file_extension.lower() == "pdf":
        return JSONResponse({"error": "file is already pdf"}, status_code=400)

    # 检查文件扩展名是否在支持的列表中
    if not any(file_url.lower().endswith(ext) for ext in supported_file_types):
        return JSONResponse({"error": f"file type not supported, given file type is: {file_extension}"}, status_code=400)

    # 创建下载tmp文件夹
    download_file_dir = pathlib.Path(__file__).parent / "tmp"
    download_file_dir.mkdir(parents=True, exist_ok=True)

    # 从URL中提取文件名，并清理可能的特殊字符
    file_name = pathlib.Path(file_url.split("/")[-1].strip('"\'\\[]'))

    # 生成唯一的下载文件路径
    timestamp = str(time.time())
    download_file_path = download_file_dir / f"{timestamp}_{file_name}"

    # 转换后的文件名和文件路径
    converted_file_name = file_name.with_suffix(".pdf")

    # 结果字典
    result = {
        "status": "success",
        "original_url": file_url,
        "converted_url": ""
    }

    try:
        # 下载文件
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url,timeout=aiohttp.ClientTimeout(total=300)) as response:
                    with open(download_file_path, "wb") as f:
                        f.write(await response.read())
            logger.info(f"File downloaded successfully, file_url: {file_url}, time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logger.error(f"Failed to download file, file_url: {file_url}, error: {e}")
            return JSONResponse({"error": "Failed to download file"}, status_code=500)

        # 将文件转换为pdf, 并保存到本地
        try:
            # 确保路径是绝对路径，并使用os.path.normpath来标准化路径
            abs_download_path = os.path.normpath(str(download_file_path.absolute()))
            abs_output_dir = os.path.normpath(str(download_file_path.parent.absolute()))
            
            logger.info(f"Converting file path: {abs_download_path}, output dir: {abs_output_dir}")
            
            process = await asyncio.create_subprocess_exec("soffice",
                                                        "--headless",
                                                        "--convert-to",
                                                        "pdf",
                                                        abs_download_path,
                                                        "--outdir",
                                                        abs_output_dir,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error(f"Failed to convert file, file_url: {file_url},abs_download_path: {abs_download_path}, abs_output_dir: {abs_output_dir}, error: {stderr.decode()}")
                # 记录更详细的错误信息
                logger.error(f"Conversion command details - File: {abs_download_path}, Output Dir: {abs_output_dir}")
                logger.error(f"Stdout: {stdout.decode() if stdout else 'None'}")
                return JSONResponse({"error": "Failed to convert file"}, status_code=500)
            else:
                logger.info(f"File conversion successful. Stdout: {stdout.decode() if stdout else 'None'}")
        except Exception as e:
            logger.error(f"Failed to convert file, file_url: {file_url}, error: {e}")
            return JSONResponse({"error": "Failed to convert file"}, status_code=500)

        # 将文件上传到s3, 并设置过期时间
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=S3_ACCESS_KEY_ID,
                aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                region_name=S3_REGION,
                endpoint_url=S3_ENDPOINT_URL)
            s3_upload_file_path = f"convert_file2pdf_server/{str(time.time())}_{str(file_name.with_suffix('.pdf'))}"
            pdf_path = download_file_path.with_suffix(".pdf")
            
            # 检查转换后的PDF文件是否存在
            if not pdf_path.exists():
                logger.error(f"Converted PDF file not found at: {pdf_path}")
                # 查看目录中的文件
                dir_files = list(download_file_path.parent.glob('*'))
                logger.info(f"Files in directory: {dir_files}")
                return JSONResponse({"error": "Converted PDF file not found"}, status_code=500)
                
            s3_client.upload_file(str(pdf_path), S3_BUCKET_NAME, str(s3_upload_file_path))
            # 设置过期时间
            if PDF_EXPIRE_TIME > 0:
                s3_client.put_object_tagging(
                    Bucket=S3_BUCKET_NAME,
                    Key=s3_upload_file_path,
                    Tagging={
                        'TagSet': [
                            {
                                'Key': 'expire_time',
                                'Value': str(int(time.time()) + PDF_EXPIRE_TIME)
                            },
                        ]
                    }
                )
            # 添加转换后的URL到结果字典
            s3_download_url = f"{S3_ENDPOINT_URL}/{S3_BUCKET_NAME}/{s3_upload_file_path}"
            if DOWNLOAD_URL_PREFIX:
                result["converted_url"] = f"{DOWNLOAD_URL_PREFIX}/{S3_BUCKET_NAME}/{s3_upload_file_path}"
            else:
                result["converted_url"] = s3_download_url
            logger.info(f"File converted successfully, upload to s3, original file_url: {file_url}, time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logger.error(f"Failed to upload file to s3, file_url: {file_url}, error: {e}")
            return JSONResponse({"error": "Failed to upload file to s3"}, status_code=500)
    finally:
        # 删除下载的原始文件
        if download_file_path.exists():
            try:
                download_file_path.unlink()
                logger.info(f"Deleted downloaded file: {download_file_path}")
            except Exception as e:
                logger.error(f"Failed to delete downloaded file: {download_file_path}, error: {e}")

        # 删除转换后的PDF文件
        pdf_path = download_file_path.with_suffix(".pdf")
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                logger.info(f"Deleted converted PDF file: {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to delete converted PDF file: {pdf_path}, error: {e}")

    return JSONResponse(result, status_code=200)


app = Starlette(routes=[Route("/health", health, methods=["GET"]),
                        Route("/get_supported_file_types", get_supported_file_types, methods=["GET"]),
                        Route("/convert", convert, methods=["POST"])],
                middleware=[Middleware(CORSMiddleware,
                                       allow_origins=["*"],
                                       allow_methods=["*"],
                                       allow_headers=["*"],
                                       allow_credentials=True,
                                       expose_headers=["*"],
                                       allow_origin_regex="https?://.*")],
                on_startup=[on_startup],
                on_shutdown=[on_shutdown])



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7758)

