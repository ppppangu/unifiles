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


async def extract_text_pages(pdf_bytes: bytes, max_concurrent_ocr: int = 3) -> List[str]:
    """核心：返回处理后的每页文本列表（如有 OCR 描述则拼接）

    Args:
        pdf_bytes: PDF 文件字节数据
        max_concurrent_ocr: 最大并发 OCR 任务数，控制内存使用
    """
    from src.logger import logger

    # 1. 在线程池里解析 PDF 结构，避免阻塞事件循环
    def _parse() -> List[Tuple[str, bool]]:
        """只解析文本和是否需要OCR，不立即生成图像"""
        results: List[Tuple[str, bool]] = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            logger.info(f"开始解析PDF，共 {len(pdf.pages)} 页")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                need_ocr = _page_need_ocr(page)
                results.append((text, need_ocr))
                if i % 10 == 0:  # 每10页记录一次进度
                    logger.info(f"已解析 {i+1}/{len(pdf.pages)} 页")
        return results

    page_info = await asyncio.to_thread(_parse)

    # 2. 分批处理需要 OCR 的页面，控制内存使用
    combined_pages: List[str] = []
    ocr_semaphore = asyncio.Semaphore(max_concurrent_ocr)

    async def _process_page_with_ocr(page_idx: int, text: str) -> str:
        """处理单个需要OCR的页面"""
        async with ocr_semaphore:
            try:
                # 在需要时才生成图像，用完立即释放
                def _generate_image() -> bytes:
                    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                        page = pdf.pages[page_idx]
                        img = page.to_image(resolution=120).original  # 降低分辨率节省内存
                        buf = BytesIO()
                        img.save(buf, format="JPEG", quality=85)  # 压缩质量
                        return buf.getvalue()

                img_bytes = await asyncio.to_thread(_generate_image)
                img = Image.open(BytesIO(img_bytes))
                ocr_result = await _describe_image(img)

                # 立即释放图像内存
                img.close()
                del img_bytes

                if ocr_result:
                    return f"{text}\n\n[图表描述]: {ocr_result}"
                else:
                    return text
            except Exception as e:
                logger.error(f"页面 {page_idx} OCR 处理失败: {e}")
                return text

    # 3. 逐页处理，对需要OCR的页面进行异步处理
    ocr_tasks = []
    for i, (text, need_ocr) in enumerate(page_info):
        if need_ocr:
            task = _process_page_with_ocr(i, text)
            ocr_tasks.append((i, task))
        else:
            combined_pages.append(text)

    # 4. 等待所有OCR任务完成
    if ocr_tasks:
        logger.info(f"开始处理 {len(ocr_tasks)} 个需要OCR的页面")
        ocr_results = await asyncio.gather(*[task for _, task in ocr_tasks], return_exceptions=True)

        # 将OCR结果插入到正确位置
        ocr_idx = 0
        final_pages = []
        for i, (text, need_ocr) in enumerate(page_info):
            if need_ocr:
                result = ocr_results[ocr_idx]
                if isinstance(result, Exception):
                    logger.error(f"页面 {i} OCR失败: {result}")
                    final_pages.append(text)
                else:
                    final_pages.append(result)
                ocr_idx += 1
            else:
                final_pages.append(text)

        return final_pages
    else:
        return [text for text, _ in page_info]