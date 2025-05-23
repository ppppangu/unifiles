import asyncio
import os
import uuid
import enum
from typing import Optional, Dict

import aiohttp
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src import pdf_utils, chunks as chunks_mod, db as db_mod  # noqa: E402

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
# FastAPI 初始化
# -----------------------------
app = FastAPI(title="RAG PDF Processing Service (refactor)")

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
    job = _JOBS[job_id]
    job.status = JobStatus.PROCESSING
    _JOBS[job_id] = job
    try:
        # 1. 提取文本（含 OCR 描述）
        text_pages = await pdf_utils.extract_text_pages(pdf_bytes)
        # 2. 分块
        text_chunks = chunks_mod.create_text_chunks(text_pages)
        # 3. 嵌入
        embeddings = await chunks_mod.embed_chunks(text_chunks)
        # 4. 写入数据库
        await db_mod.insert_chunks(text_chunks, embeddings, knowledge_base_id, document_id)
        job.status = JobStatus.SUCCESS
        job.message = f"已写入 {len(text_chunks)} chunks"
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.message = str(exc)
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

    # 仅实现 simple
    if mode != "simple":
        raise HTTPException(status_code=400, detail="目前仅支持 simple 模式")

    # 解析 PDF 来源
    if pdf_file_url:
        pdf_bytes = await _download_pdf(pdf_file_url)
    elif pdf_file is not None:
        pdf_bytes = await pdf_file.read()
    else:
        raise HTTPException(status_code=400, detail="pdf_file_url 与 pdf_file 必须至少提供一个")

    # 后台处理
    background_tasks.add_task(_process_simple_mode, job_id, knowledge_base_id, document_id, pdf_bytes)

    return {"status": "accepted", "job_id": job_id}


@app.get("/jobs/{job_id}")
async def query_job(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id 未找到")
    return job


@app.get("/health")
async def health_check():
    return {"status": "healthy"}