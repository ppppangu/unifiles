import asyncio
import os
import uuid
import enum
from typing import Optional, Dict
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src import pdf_utils, chunks as chunks_mod, db as db_mod  # noqa: E402
from src.logger import logger

# -----------------------------
# 内存级任务状态缓存（简易版）
# -----------------------------
class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.QUEUED
    message: Optional[str] = None


_JOBS: Dict[str, Job] = {}


# -----------------------------
# 应用生命周期管理
# -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("===================应用启动====================")
    logger.info("RAG PDF Processing Service 开始启动")
    # 这里可以添加其他启动时需要执行的代码，如数据库连接检查等

    yield

    # 关闭时执行
    logger.info("应用关闭")
    logger.info("===================应用关闭====================")

# -----------------------------
# FastAPI 初始化
# -----------------------------
logger.info("初始化 FastAPI 应用")
app = FastAPI(
    title="RAG PDF Processing Service (refactor)",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# 工具函数
# -----------------------------
async def _download_pdf(url: str) -> bytes:
    """从公网 URL 异步下载 PDF 文件"""
    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载 PDF 失败: {e}")


async def _process_simple_mode(job_id: str,
                               knowledge_base_id: str,
                               document_id: str,
                               pdf_bytes: bytes):
    """simple 模式完整流水线"""
    logger.info(f"开始处理任务 job_id={job_id}, knowledge_base_id={knowledge_base_id}, document_id={document_id}")
    job = _JOBS[job_id]
    job.status = JobStatus.PROCESSING
    _JOBS[job_id] = job
    try:
        # 1. 提取文本（含 OCR 描述）
        logger.info(f"[{job_id}] 步骤1: 开始提取文本")
        text_pages = await pdf_utils.extract_text_pages(pdf_bytes)
        logger.info(f"[{job_id}] 步骤1: 文本提取完成，共 {len(text_pages)} 页")

        # 2. 分块
        logger.info(f"[{job_id}] 步骤2: 开始文本分块")
        text_chunks = chunks_mod.create_text_chunks(text_pages)
        logger.info(f"[{job_id}] 步骤2: 文本分块完成，共 {len(text_chunks)} 个块")

        # 3. 嵌入
        logger.info(f"[{job_id}] 步骤3: 开始生成嵌入向量")
        embeddings = await chunks_mod.embed_chunks(text_chunks)
        logger.info(f"[{job_id}] 步骤3: 嵌入向量生成完成")

        # 4. 写入数据库
        logger.info(f"[{job_id}] 步骤4: 开始写入数据库")
        await db_mod.insert_chunks(text_chunks, embeddings, knowledge_base_id, document_id)
        logger.info(f"[{job_id}] 步骤4: 数据库写入完成")

        job.status = JobStatus.SUCCESS
        job.message = f"已写入 {len(text_chunks)} chunks"
        logger.info(f"[{job_id}] 任务处理成功: {job.message}")
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = str(exc)
        logger.error(f"[{job_id}] 任务处理失败: {str(exc)}", exc_info=True)
        raise
    finally:
        _JOBS[job_id] = job


# -----------------------------
# API 端点
# -----------------------------
@app.post("/process-pdf/")
async def process_pdf_endpoint(
    background_tasks: BackgroundTasks,
    knowledge_base_id: str = Form(...),
    document_id: str = Form(...),
    pdf_file_url: Optional[str] = Form(None),
    pdf_file: Optional[UploadFile] = File(None),
    job_id: Optional[str] = Form(None),
    mode: str = Form("simple"),
):
    # 生成 / 回收 job_id
    job_id = job_id or str(uuid.uuid4())
    _JOBS[job_id] = Job(id=job_id)

    logger.info(f"收到PDF处理请求: job_id={job_id}, knowledge_base_id={knowledge_base_id}, document_id={document_id}, mode={mode}")

    # 仅实现 simple
    if mode != "simple":
        logger.warning(f"不支持的处理模式: {mode}")
        raise HTTPException(status_code=400, detail="目前仅支持 simple 模式")

    # 解析 PDF 来源
    try:
        if pdf_file_url:
            logger.info(f"[{job_id}] 从URL下载PDF: {pdf_file_url}")
            pdf_bytes = await _download_pdf(pdf_file_url)
            logger.info(f"[{job_id}] PDF下载成功，大小: {len(pdf_bytes)/1024:.2f} KB")
        elif pdf_file is not None:
            logger.info(f"[{job_id}] 从上传文件读取PDF: {pdf_file.filename}")
            pdf_bytes = await pdf_file.read()
            logger.info(f"[{job_id}] PDF读取成功，大小: {len(pdf_bytes)/1024:.2f} KB")
        else:
            logger.warning(f"[{job_id}] 未提供PDF来源")
            raise HTTPException(status_code=400, detail="pdf_file_url 与 pdf_file 必须至少提供一个")
    except Exception as e:
        logger.error(f"[{job_id}] PDF获取失败: {str(e)}", exc_info=True)
        raise

    # 后台处理
    logger.info(f"[{job_id}] 添加后台任务处理PDF")
    background_tasks.add_task(_process_simple_mode, job_id, knowledge_base_id, document_id, pdf_bytes)

    return {"status": "accepted", "job_id": job_id}


@app.get("/jobs/{job_id}")
async def query_job(job_id: str):
    logger.debug(f"查询任务状态: job_id={job_id}")
    job = _JOBS.get(job_id)
    if not job:
        logger.warning(f"任务不存在: job_id={job_id}")
        raise HTTPException(status_code=404, detail="job_id 未找到")
    logger.debug(f"任务状态: job_id={job_id}, status={job.status}, message={job.message}")
    return job


@app.get("/health")
async def health_check():
    logger.debug("健康检查请求")
    return {"status": "healthy"}