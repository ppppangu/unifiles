import asyncio
from typing import List

import aiohttp

from singleton_mode.singleton_embedding import get_latest_embedding_instance

# ------------------------------------
# 文本分块
# ------------------------------------

def create_text_chunks(text_pages: List[str], chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """滑动窗口分块"""
    combined = "\n".join(text_pages)
    total_len = len(combined)
    if total_len <= chunk_size:
        return [combined]

    chunks: List[str] = []
    start = 0
    while start < total_len:
        end = min(start + chunk_size, total_len)
        chunks.append(combined[start:end])
        start = end - overlap
    return chunks


# ------------------------------------
# 嵌入获取
# ------------------------------------

async def _embedding_request(text: str, session: aiohttp.ClientSession) -> List[float]:
    model_name, base_url, api_key = get_latest_embedding_instance()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "input": text,
    }
    async with session.post(base_url, headers=headers, json=payload, timeout=60) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data["data"][0]["embedding"]


async def embed_chunks(chunks: List[str], batch_size: int = 10, max_concurrent: int = 5) -> List[List[float]]:
    """分批生成嵌入向量，控制内存使用和并发数

    Args:
        chunks: 文本块列表
        batch_size: 每批处理的块数
        max_concurrent: 最大并发请求数
    """
    from src.logger import logger

    if not chunks:
        return []

    logger.info(f"开始生成 {len(chunks)} 个文本块的嵌入向量，批大小: {batch_size}")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _embedding_request_with_limit(text: str, session: aiohttp.ClientSession) -> List[float]:
        async with semaphore:
            return await _embedding_request(text, session)

    all_embeddings = []

    async with aiohttp.ClientSession() as session:
        # 分批处理
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            logger.info(f"处理第 {i//batch_size + 1} 批，共 {len(batch)} 个块")

            # 批内并发处理
            tasks = [_embedding_request_with_limit(chunk, session) for chunk in batch]
            batch_embeddings = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理异常
            for j, embedding in enumerate(batch_embeddings):
                if isinstance(embedding, Exception):
                    logger.error(f"块 {i+j} 嵌入生成失败: {embedding}")
                    # 使用零向量作为fallback
                    all_embeddings.append([0.0] * 1536)  # 假设1536维
                else:
                    all_embeddings.append(embedding)

            # 小批量间隔，避免API限流
            if i + batch_size < len(chunks):
                await asyncio.sleep(0.1)

    logger.info(f"嵌入向量生成完成，共 {len(all_embeddings)} 个")
    return all_embeddings