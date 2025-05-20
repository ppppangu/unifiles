"""文件上传的服务器，提供文件上传，以及多种预定义的处理模式，上传完成后返回处理结果的结果所在位置，不提供文件本地存储服务。代码保持间接性，不写不必要的注释"""

# 导入依赖
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import asyncio
import aiohttp
import aiofiles
import aiosqlite
import asyncpg

import boto3
import ast
import uvicorn

import os
from loguru import logger
from pathlib import Path
from datetime import datetime

from src.vector_process import VectorProcess
from src.mineru_client import MinerUClient
from src.extra_user_infomation import get_user_id_by_knowledge_base_id

from src.tools import async_get_s3_connection

# 调试使用
#S3
os.environ["FILE_SERVER_S3_ENDPOINT_URL"]="http://1.tcp.cpolar.cn:21729"
os.environ["FILE_SERVER_S3_ACCESS_KEY"]="N3r+Mh2:z4w)LK=a8e%N"
os.environ["FILE_SERVER_S3_SECRET_ACCESS_KEY"]="N3r+Mh2:z4w)LK=a8e%N"
os.environ["FILE_SERVER_S3_BUCKET_NAME"]="users"
os.environ["FILE_SERVER_S3_REGION"]="us-east-1"

# vector_db(postgres)  数据库的配置信息
os.environ["FILE_SERVER_POSTGRES_HOST"]="192.168.132.149"
os.environ["FILE_SERVER_POSTGRES_PORT"]="5437"
os.environ["FILE_SERVER_POSTGRES_USER"]="postgres"
os.environ["FILE_SERVER_POSTGRES_PASSWORD"]="postgres"
os.environ["FILE_SERVER_POSTGRES_DATABASE"]="postgres"

# MinerUAPIList
os.environ["FILE_SERVER_MINERU_URL_LIST"]="['http://192.168.132.149:8888']"

# 获取环境变量
FILE_SERVER_S3_ENDPOINT_URL = os.getenv("FILE_SERVER_S3_ENDPOINT_URL")
FILE_SERVER_S3_ACCESS_KEY = os.getenv("FILE_SERVER_S3_ACCESS_KEY")
FILE_SERVER_S3_SECRET_ACCESS_KEY = os.getenv("FILE_SERVER_S3_SECRET_ACCESS_KEY")
FILE_SERVER_S3_BUCKET_NAME = os.getenv("FILE_SERVER_S3_BUCKET_NAME")
FILE_SERVER_S3_REGION = os.getenv("FILE_SERVER_S3_REGION")
FILE_SERVER_POSTGRES_HOST = os.getenv("FILE_SERVER_POSTGRES_HOST")
FILE_SERVER_POSTGRES_PORT = os.getenv("FILE_SERVER_POSTGRES_PORT")
FILE_SERVER_POSTGRES_USER = os.getenv("FILE_SERVER_POSTGRES_USER")
FILE_SERVER_POSTGRES_PASSWORD = os.getenv("FILE_SERVER_POSTGRES_PASSWORD")
FILE_SERVER_POSTGRES_DATABASE = os.getenv("FILE_SERVER_POSTGRES_DATABASE")
FILE_SERVER_MINERU_URL_LIST = ast.literal_eval(os.getenv("FILE_SERVER_MINERU_URL_LIST"))

# 设置日志文件的目录和文件
logs_path = Path(__file__).parent / "logs"
logs_path.mkdir(mode=777, exist_ok=True)

# 设置临时文件的下载目录
temp_path = Path(__file__).parent / "tmp"
temp_path.mkdir(mode=777, exist_ok=True)

# 设置用于记录任务进度的db文件的路径
db_path = Path(__file__).parent / "job.db"
db_path.touch(exist_ok=True)

async def homepage(request: Request):
    return JSONResponse({"message": "Hello, World!"})

async def health(request: Request):
    return JSONResponse({"status": "ok"})

async def get_mode(request: Request):
    return JSONResponse(
        {
            "mode": ["vector","graph"]
        }
    )

async def upload(request: Request):
    # parase and validate
    form = await request.form()

    # 解析请求参数
    knowledge_base_id = form.get("knowledge_base_id")
    document_id = form.get("document_id")
    user_id = form.get("user_id")
    job_id = form.get("job_id")
    file_url = form.get("pdf_file_url")
    mode = form.getlist("mode")
    parse_method = form.get("parse_method")

    # validate
    if not any([knowledge_base_id,document_id,file_url]):
        return JSONResponse({"status": "error", "message": "knowledge_base_id / document_id / pdf_file_url are required"}, status_code=400)
    if not mode:
        mode = ["vector"]
    if not parse_method:
        parse_method = "auto"
    if not user_id:
        return JSONResponse({"status": "error", "message": "user_id is required"}, status_code=400)
    else:
        # Create a database connection
        conn = await asyncpg.connect(
            host=FILE_SERVER_POSTGRES_HOST,
            port=int(FILE_SERVER_POSTGRES_PORT),
            user=FILE_SERVER_POSTGRES_USER,
            password=FILE_SERVER_POSTGRES_PASSWORD,
            database=FILE_SERVER_POSTGRES_DATABASE
        )
        try:
            user_id = await get_user_id_by_knowledge_base_id(knowledge_base_id, conn)
            if not user_id:
                return JSONResponse({"status": "error", "message": "there is no user_id for this knowledge_base_id, please user_id and knowledge_base_id are whether match"}, status_code=400)
        finally:
            await conn.close()

    # 下载并保存文件
    # async with aiohttp.ClientSession() as session:
    #     async with session.get(file_url,timeout=aiohttp.ClientTimeout(total=300)) as response:
    #         file_content = await response.read()
    #         file_save_name = file_url.split("/")[-1]
    #         file_path = temp_path / file_name
    #         async with aiofiles.open(file_path, mode="wb") as f:
    #             await f.write(file_content)

    file_name = file_url.split("/")[-1]

    logger.info("================================================")
    logger.info("------------------------------------------------")
    logger.info(f"user_id: {user_id}")
    logger.info(f"knowledge_base_id: {knowledge_base_id}")
    logger.info(f"document_id: {document_id}")
    logger.info(f"upload file: {file_name}")
    logger.info(f"mode: {mode}")
    logger.info(f"file_size: {len(file_content)}")
    logger.info("------------------------------------------------")

    if "vector" in mode:
        pg_connection = await asyncpg.connect(
            host=FILE_SERVER_POSTGRES_HOST,
            port=int(FILE_SERVER_POSTGRES_PORT),
            user=FILE_SERVER_POSTGRES_USER,
            password=FILE_SERVER_POSTGRES_PASSWORD,
            database=FILE_SERVER_POSTGRES_DATABASE
        )
        s3_connection = await async_get_s3_connection(
            FILE_SERVER_S3_ENDPOINT_URL,
            FILE_SERVER_S3_ACCESS_KEY,
            FILE_SERVER_S3_SECRET_ACCESS_KEY,
            FILE_SERVER_S3_REGION
        )
        mineru_client = MinerUClient(
            mineru_url=FILE_SERVER_MINERU_URL,
            file_content=file_content,
            s3_connection=s3_connection,
            bucket_name=FILE_SERVER_S3_BUCKET_NAME,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            parse_method=parse_method
        )
        vector_process = VectorProcess(
            pdf=file_content,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_name=file_name,
            pg_connection=pg_connection,
            s3_connection=s3_connection,
            bucket_name=FILE_SERVER_S3_BUCKET_NAME,
            mineru_client=mineru_client
        )
        await vector_process.ocr()
    if "graph" in mode: ...

    logger.info("================================================")
    return JSONResponse({"status": "ok"})

async def start_up():
    # 设置日志
    log_path = str(logs_path / f"{datetime.now().strftime('%Y-%m-%d')}.log")
    logger.add(log_path, enqueue=True, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",level="INFO")

    logger.info("===================start up====================")
    logger.info("file server begin to start up!")
    
    # 检查向量数据库连接
    try:
        test_pg_connection = await asyncpg.connect(
            host=FILE_SERVER_POSTGRES_HOST,
            port=int(FILE_SERVER_POSTGRES_PORT),
            user=FILE_SERVER_POSTGRES_USER,
            password=FILE_SERVER_POSTGRES_PASSWORD,
            database=FILE_SERVER_POSTGRES_DATABASE
        )
        await test_pg_connection.close()
        logger.info(f"vector database connection test passed! | Vector database(postgres) is working on {FILE_SERVER_POSTGRES_HOST}:{FILE_SERVER_POSTGRES_PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL, config_url: postgres://{FILE_SERVER_POSTGRES_USER}:{FILE_SERVER_POSTGRES_PASSWORD}@{FILE_SERVER_POSTGRES_HOST}:{FILE_SERVER_POSTGRES_PORT}/{FILE_SERVER_POSTGRES_DATABASE}, error: {e}")
    finally:
        try:
            await test_pg_connection.close()
        except Exception as e:
            pass

    # 检查S3连接
    try:
        # 使用自定义配置创建S3客户端
        test_s3_connection = await async_get_s3_connection(FILE_SERVER_S3_ENDPOINT_URL, FILE_SERVER_S3_ACCESS_KEY, FILE_SERVER_S3_SECRET_ACCESS_KEY, FILE_SERVER_S3_REGION)
        await test_s3_connection.list_buckets()
        logger.info(f"s3 connection test passed!              | S3 is working on {FILE_SERVER_S3_ENDPOINT_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to S3, config_url: s3://{FILE_SERVER_S3_ACCESS_KEY}:{FILE_SERVER_S3_SECRET_ACCESS_KEY}@{FILE_SERVER_S3_ENDPOINT_URL}, error: {e}")
    finally:
        try:
            await test_s3_connection.close()
        except Exception as e:
            pass

    # 检查MinerU的服务端连接
    for mineru_url in FILE_SERVER_MINERU_URL_LIST:
        try:
            test_s3_connection = await async_get_s3_connection(FILE_SERVER_S3_ENDPOINT_URL, FILE_SERVER_S3_ACCESS_KEY, FILE_SERVER_S3_SECRET_ACCESS_KEY, FILE_SERVER_S3_REGION)
            await test_s3_connection.list_buckets()
            mineru_client = MinerUClient(
                mineru_url=mineru_url,
                file_content=None,
                s3_connection=test_s3_connection
            )
            await mineru_client.health()
            logger.info(f"mineru connection test passed!          | MinerU is working on {mineru_url}")
        except Exception as e:
            logger.error(f"Failed to initialize MinerUClient, mineru_url: {mineru_url}, error: {e}")
        finally:
            try:
                await test_s3_connection.close()
            except Exception as e:
                pass
    
    # 创建用于记录任务的db文件
    if not db_path.exists():
        try:
            async with aiosqlite.connect(db_path) as db:

                # 【持久增量记录】创建任务表，任务调度从这里确定，status有pedding(就是接收到任务等待调度)，running(就是正在运行)，completed(就是运行完成)，failed(就是任务失败)
                await db.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    knowledge_base_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    file_url TEXT NOT NULL,
                    mode TEXT NOT NULL, 
                    status TEXT NOT NULL
                )
                ''')

                # 【持久增量记录】创建ocr任务表，ocr任务调度从这里确定
                await db.execute('''
                CREATE TABLE IF NOT EXISTS ocr_jobs (
                    id INTEGER PRIMARY KEY,
                    parse_method TEXT NOT NULL,
                    recive_time TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    run_result TEXT NOT NULL,
                    run_result_detail TEXT NOT NULL,
                    mineru_url TEXT NOT NULL
                )
                ''')

                # 【临时调度记录】先删除mineru管理表，再创建
                await db.execute('''
                DROP TABLE IF EXISTS mineru_manager
                ''')

                # 【临时调度记录】创建mineru管理表，mineru管理表用来自动调配ocr在哪个mineru端口上运行，同时记录已经存在的mineru端口的所有记录
                await db.execute('''
                CREATE TABLE IF NOT EXISTS mineru_manager (
                    id INTEGER PRIMARY KEY,
                    mineru_url TEXT NOT NULL,
                    RUNNING_JOB_ID TEXT
                )
                ''')
                
                # 提交更改
                await db.commit()
        finally:
            try:
                await db.close()
            except Exception as e:
                pass
    else:
        logger.info("job db init success")
    logger.info("==================start up=======================")


middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(
    middleware=middleware,
    routes=[
        Route("/", homepage,methods=["GET"]),
        Route("/health", health,methods=["GET"]),
        Route("/get_mode", get_mode,methods=["GET"]),
        Route("/upload", upload,methods=["POST"])
    ],
    on_startup=[start_up]
)

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)