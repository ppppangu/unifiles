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


async def embed_chunks(chunks: List[str]) -> List[List[float]]:
    async with aiohttp.ClientSession() as session:
        tasks = [_embedding_request(c, session) for c in chunks]
        return await asyncio.gather(*tasks) 