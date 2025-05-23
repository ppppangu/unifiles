import asyncio
import base64
from io import BytesIO
from typing import List, Tuple

import aiohttp
import pdfplumber
from PIL import Image

from singleton_mode.singleton_multimodal_embedding import (
    get_latest_multimodal_embedding_instance,
)


# -----------------------------
# 检测工具
# -----------------------------

def _page_need_ocr(page: "pdfplumber.page.Page") -> bool:
    """粗略判断页面是否含表格或图片"""
    has_table = len(page.extract_tables()) > 0
    has_image = len(page.images) > 0
    return has_table or has_image


async def _describe_image(img: Image.Image) -> str:
    """调用多模态 LLM 对图片进行描述"""
    model_name, base_url, api_key = get_latest_multimodal_embedding_instance()

    # 转成 base64
    buf = BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请描述这张图片或表格的内容。",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                ],
            }
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(base_url, headers=headers, json=payload, timeout=120) as resp:
            resp.raise_for_status()
            data = await resp.json()
            # zhipu glm 兼容 resp 取法
            try:
                return data["choices"][0]["message"]["content"]
            except Exception:
                return ""


async def extract_text_pages(pdf_bytes: bytes) -> List[str]:
    """核心：返回处理后的每页文本列表（如有 OCR 描述则拼接）"""

    # 1. 在线程池里解析 PDF 结构，避免阻塞事件循环
    def _parse() -> List[Tuple[str, bool, bytes | None]]:
        results: List[Tuple[str, bool, bytes | None]] = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                need_ocr = _page_need_ocr(page)
                img_bytes: bytes | None = None
                if need_ocr:
                    img = page.to_image(resolution=150).original
                    buf = BytesIO()
                    img.save(buf, format="JPEG")
                    img_bytes = buf.getvalue()
                results.append((text, need_ocr, img_bytes))
        return results

    page_info = await asyncio.to_thread(_parse)

    # 2. 对需要 OCR 的页面并发调用多模态模型
    tasks = [
        _describe_image(Image.open(BytesIO(img))) if need and img else None
        for (_, need, img) in page_info
    ]

    # 填充占位
    ocr_results: List[str | None] = []
    if tasks:
        # 保留 None 位置
        tasks_filter = [t for t in tasks if t is not None]
        if tasks_filter:
            ocr_texts = await asyncio.gather(*tasks_filter, return_exceptions=True)
        else:
            ocr_texts = []
        idx = 0
        for t in tasks:
            if t is None:
                ocr_results.append(None)
            else:
                res = ocr_texts[idx]
                idx += 1
                if isinstance(res, Exception):
                    ocr_results.append(None)
                else:
                    ocr_results.append(res)
    else:
        ocr_results = []

    # 3. 组合文本
    combined_pages: List[str] = []
    for (text, need, _), ocr in zip(page_info, ocr_results):
        if need and ocr:
            combined_pages.append(f"{text}\n\n[图表描述]: {ocr}")
        else:
            combined_pages.append(text)

    return combined_pages 