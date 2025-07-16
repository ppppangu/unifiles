import asyncio
import httpx
import aiohttp
from pathlib import Path
import uuid
import pdfplumber
import aiofiles
import os
import warnings
import re
from minio import Minio
import yaml
from loguru import logger
from singleton_embedding import get_latest_embedding_instance
import json
import asyncpg
from typing import Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.tools import detect_content_type, convert_to_internal_minio_url

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# 忽略pdfplumber的警告 - 全局设置
warnings.filterwarnings("ignore", category=UserWarning, module='pdfminer')

def plumber_read_pdf_page(file_url: str, page_num: int = 0):
    with pdfplumber.open(file_url) as pdf:
        page = pdf.pages[page_num]
        return page.extract_text()

def plumber_read_pdf_page_number(file_url: str):
    with pdfplumber.open(file_url) as pdf:
        return len(pdf.pages)

async def plumber_read_pdf(file_url: str):
    # 获取pdf文件的页数
    page_number = await asyncio.to_thread(plumber_read_pdf_page_number, file_url)
    text = ""
    # 读取pdf文件
    tasks = [asyncio.to_thread(plumber_read_pdf_page, file_url, page_num) for page_num in range(page_number)]
    results = await asyncio.gather(*tasks)
    for result in results:
        text += result
    return text

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, httpx.ProtocolError))
)
async def describe_photo(photo_url: str,index:int,alias:str = ""):
    # 使用多模态大模型，描述图片，需要带重试机制
    if not alias:
        mode = "multimodal_llm"
        name,url,key,alias = get_latest_embedding_instance(instance_type=mode)
    else:
        name,url,key,alias = get_latest_embedding_instance(alias=alias)
    # 准备请求头 - 只有当key不为空时才添加Authorization header
    headers = {}
    if key and key.strip():
        headers["Authorization"] = f"Bearer {key}"

    data = {
        "model": name,
        "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"{photo_url}"}}]},{"role": "user", "content": [{"type": "text", "text": "请详细这张图片的内容"}]}],
        "stream": False
    }

    try:
        # 配置更宽松的HTTP客户端
        timeout = httpx.Timeout(
            connect=30.0,
            read=60.0,
            write=30.0,
            pool=30.0
        )
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=50,
            keepalive_expiry=30.0
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=False,
            verify=False
        ) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()  # 自动处理HTTP错误
            description = response.json()
            return index,description["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"图片描述请求失败: {str(e)}, URL: {url}, 错误类型: {type(e).__name__}")
        raise
        
def find_all_text_and_image_index(text: str, user_id: str, knowledge_base_id: str, document_id: str,describe_photo:bool=False):
    """
    找到文本中所有图片和文本片段的索引位置，并将相对图片路径转换为绝对MinIO URLs

    Args:
        text: 输入的markdown文本
        user_id: 用户ID
        knowledge_base_id: 知识库ID
        document_id: 文档ID

    Returns:
        tuple: (converted_text, results)
            - converted_text: 转换后的markdown文本，图片路径已转换为绝对URLs
            - results: 包含元组的列表，每个元组为(开始索引, 结束索引, 类型)
                      类型为"image"或"text"
    """
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    # 返回的结果列表是一个列表，列表的元素为元组，元组第一个元素为开始索引，元组第二个元素为结束索引，元组第三个元素为"image"或"text"
    results = []

    # 首先找到所有图片的位置
    image_matches = []
    for match in re.finditer(pattern, text):
        image_matches.append((match.start(), match.end(), "image"))

    # 按开始位置排序
    image_matches.sort(key=lambda x: x[0])

    # 现在填充文本片段
    text_length = len(text)
    current_pos = 0

    for image_start, image_end, _ in image_matches:
        # 如果当前位置到图片开始位置之间有文本，添加文本片段
        if current_pos < image_start:
            results.append((current_pos, image_start, "text"))

        # 添加图片片段
        results.append((image_start, image_end, "image"))

        # 更新当前位置到图片结束位置
        current_pos = image_end

    # 处理剩余文本的逻辑：区分有图片和无图片的情况
    if image_matches:
        # 如果有图片，检查最后一个图片后面是否还有文本
        if current_pos < text_length:
            results.append((current_pos, text_length, "text"))
    else:
        # 如果没有找到任何图片，整个文本都是文本片段
        if text_length > 0:
            results.append((0, text_length, "text"))

    # 按开始位置排序结果
    results.sort(key=lambda x: x[0])

    # 构建转换后的文本，将相对图片路径转换为绝对MinIO URLs
    converted_text = ""

    for start, end, type_ in results:
        if type_ == "text":
            # 直接添加文本片段
            converted_text += text[start:end]
        elif type_ == "image":
            # 提取图片markdown并转换URL
            image_markdown = text[start:end]

            # 使用正则表达式解析图片markdown
            match = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', image_markdown)
            if match:
                alt_text = match.group(1)
                image_path = match.group(2)

                # 转换相对路径为绝对MinIO URL
                if image_path.startswith("/"):
                    # 如果以/开头，则是相对路径，需要去掉/
                    absolute_url = f"{config['server_components']['minio']['public_url_prefix']}/{config['server_components']['minio']['bucket_name']}/{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path[1:]}"
                else:
                    # 相对路径，直接拼接
                    absolute_url = f"{config['server_components']['minio']['public_url_prefix']}/{config['server_components']['minio']['bucket_name']}/{user_id}/knowledge_base/{knowledge_base_id}/{document_id}/{image_path}"

                # 重新构建markdown
                converted_markdown = f"![{alt_text}]({absolute_url})"
                converted_text += converted_markdown
            else:
                # 如果解析失败，保持原样
                converted_text += image_markdown

    # 返回转换后的文本和原始的索引结果
    return converted_text, results

# 同步方法
def save_results_to_json_sync(converted_text: str, results: list):
    # 将results转为字典列表，存成json文件
    results_dict = []
    for index, result in enumerate(results):
        results_dict.append({
            "content": converted_text[result[0]:result[1]],
            "index": index,
            "type": result[2],
            "embedding": None
        })
    results_dict.sort(key=lambda x: x["index"])
    return results_dict
    
# 提取一个![](url)中的url
def extract_photo_url(photo_url: str):
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.search(pattern, photo_url)
    if matches:
        return matches.group(2)
    return None

# 将一个![xxx](url)中的xxx替换为desctiption_text，url部分不变
def replace_photo_text(raw_text: str,description_text: str):
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.search(pattern, raw_text)
    if matches:
        return f"![{description_text}]({matches.group(2)})"
    return raw_text

# 将results转为字典列表，存成json文件
async def save_results_to_json(converted_text: str, results: list, file_path: str):
    """
    将results转为字典列表，存成json文件

    Args:
        converted_text: 转换后的文本内容
        results: 包含元组的列表，每个元组为(开始索引, 结束索引, 类型)
        file_path: 保存的json文件路径

    Returns:
        None

    生成的字典结构:
        - content: 文本或图片的内容
        - index: 在文档中的分块索引
        - type: 内容类型 ("text" 或 "image")
        - embedding: 向量嵌入（初始为空，后续可填充）
    """
    # 两步：
    # 第一步
    # 将results转为字典列表，存成json文件
    results_dict = await asyncio.to_thread(save_results_to_json_sync,converted_text,results)
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(results_dict, ensure_ascii=False, indent=2))
    # 第二步，描述图片，将原来属于![](url)的图片元素，让大模型描述文本得到desctiption_text，将desctiption_text替换掉[]里的内容，变为![desctiption_text](url)，存成json文件
    # 分配任务
    tasks = [describe_photo(extract_photo_url(result["content"]),index) for index,result in enumerate(results_dict) if result["type"] == "image"]
    results = await asyncio.gather(*tasks)
    for index,result in results:
        results_dict[index]["content"] = replace_photo_text(results_dict[index]["content"],result)
    # 将results_dict存成json文件
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(results_dict, ensure_ascii=False, indent=2))
    logger.info(f"保存results_dict到json文件成功，共{len(results_dict)}个条目，文件路径: {file_path}")

# 将文本进行分块策略
async def split_text(text: str, mode: str, module: str):
    """
    根据指定的模式和模块对文本进行分块

    Args:
        text: 要分块的文本
        mode: 分块模式，如"SlidingWindow"
        module: 分块模块，如"normal"

    Returns:
        list: 分块后的文本列表
    """
    # 根据mode和module选择分块策略
    if mode == "SlidingWindow":
        if module == "normal":
            new_text = []
            chunk_size = config["text_chunk_strategy"]["SlidingWindow"]["chunk_size"]
            chunk_overlap = config["text_chunk_strategy"]["SlidingWindow"]["chunk_overlap"]

            # 如果文本长度小于等于chunk_size，直接返回原文本
            if len(text) <= chunk_size:
                return [text] if text.strip() else []

            # 滑动窗口分块策略
            start = 0
            while start < len(text):
                # 计算当前块的结束位置
                end = start + chunk_size

                # 如果这是最后一块，确保包含所有剩余文本
                if end >= len(text):
                    chunk = text[start:]
                    if chunk.strip():  # 只添加非空块
                        new_text.append(chunk)
                    break
                else:
                    chunk = text[start:end]
                    if chunk.strip():  # 只添加非空块
                        new_text.append(chunk)

                # 计算下一个块的起始位置（考虑重叠）
                start = end - chunk_overlap

                # 防止无限循环：如果重叠大于等于块大小，强制前进
                if chunk_overlap >= chunk_size:
                    start = end

            return new_text

    # 如果没有匹配的模式，返回原文本作为单个块
    return [text] if text.strip() else []


# 将json文件中的文本进行分块策略，第一步出来的json中将文本和图片分开了，但是文本图片部分不动，但是位置顺延 
async def split_text_by_json(json_file_path: str):
    # 读取json文件
    async with aiofiles.open(json_file_path, "r", encoding="utf-8") as f:
        results_dict = json.loads(await f.read())

    results_dict.sort(key=lambda x: x["index"])
    new_results_dict_list = []
    # 将文本进行分块策略
    for item in results_dict:
        if item["type"] == "text":
            text_content = item["content"]
            text_chunks = await split_text(text_content, "SlidingWindow", "normal")
            for chunk in text_chunks:
                new_results_dict_list.append({"content": chunk, "index": len(new_results_dict_list), "type": "text", "embedding": None})
        else:
            new_results_dict_list.append({"content": item["content"], "index": len(new_results_dict_list), "type": item["type"], "embedding": None})
    # 将new_results_dict_list存成json文件
    async with aiofiles.open(json_file_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(new_results_dict_list, ensure_ascii=False, indent=2))
    logger.info(f"将json文件中的文本进行分块策略成功,覆写原文件，共{len(new_results_dict_list)}个条目，文件路径: {json_file_path}")

# 将一个文本存入指定用户的指定知识库的指定文档的文本表
async def save_text_to_vcdb_text_table(
    text: str,
    document_id: str,
    document_name: str,
    user_id: str,
    knowledge_base_id: str,
    chunk_id: Optional[str] = None,
    doc_position: Optional[int] = None,
    embedding: Optional[List[float]] = None
) -> str:
    """
    保存文本段到chunk_schema.chunks表的基础函数

    该函数将文本插入到chunks表，触发器会自动：
    1. 同步数据到components表 (sync_chunks_to_components)
    2. 确保doc_position唯一性 (ensure_doc_position_uniqueness)
    3. 更新全文搜索索引 (update_component_tsv)
    4. 更新文档内容和组件ID数组 (update_document_content, update_component_document_ids)

    增强的验证逻辑：
    - 验证用户是否存在，不存在则创建
    - 验证知识库是否存在，不存在则创建
    - 验证文档是否存在，不存在则创建

    Args:
        text: 文本内容
        document_id: 文档ID (外键引用)
        user_id: 用户ID (用于上下文和验证)
        knowledge_base_id: 知识库ID (用于上下文和验证)
        chunk_id: 文本块ID，如果为None则自动生成UUID
        doc_position: 文档位置，如果为None则由触发器自动分配
        embedding: 向量嵌入，如果为None则不设置

    Returns:
        str: 插入的文本块ID

    Raises:
        ValueError: 参数验证失败
        Exception: 数据库操作失败
    """
    # 参数验证
    if not text or not text.strip():
        raise ValueError("Text content cannot be empty")
    if not document_id:
        raise ValueError("document_id is required")
    if not user_id:
        raise ValueError("user_id is required")
    if not knowledge_base_id:
        raise ValueError("knowledge_base_id is required")

    # 生成文本块ID（如果未提供）
    if chunk_id is None:
        chunk_id = str(uuid.uuid4())

    # 获取数据库配置
    pg_config = config["server_components"]["pg_vector"]

    try:
        # 建立数据库连接
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=int(pg_config["port"]),
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )

        try:
            async with conn.transaction():
                # 1. 验证并创建用户（如果不存在）
                user_check_query = "SELECT id FROM chunk_schema.users WHERE id = $1"
                user_result = await conn.fetchrow(user_check_query, user_id)

                if not user_result:
                    logger.info(f"User {user_id} not found, creating new user")
                    user_insert_query = """
                        INSERT INTO chunk_schema.users (id, knowledge_ids)
                        VALUES ($1, '{}')
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(user_insert_query, user_id)
                    logger.info(f"Successfully created user {user_id}")

                # 2. 验证并创建知识库（如果不存在）
                kb_check_query = """
                    SELECT id FROM chunk_schema.knowledge_bases
                    WHERE id = $1 AND user_id = $2
                """
                kb_result = await conn.fetchrow(kb_check_query, knowledge_base_id, user_id)

                if not kb_result:
                    logger.info(f"Knowledge base {knowledge_base_id} not found for user {user_id}, creating new knowledge base")
                    kb_insert_query = """
                        INSERT INTO chunk_schema.knowledge_bases (id, user_id, name, description, document_ids)
                        VALUES ($1, $2, $3, $4, '{}')
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(kb_insert_query, knowledge_base_id, user_id,
                                     f"Knowledge Base {knowledge_base_id}",
                                     f"Auto-created knowledge base for user {user_id}")
                    logger.info(f"Successfully created knowledge base {knowledge_base_id}")

                # 3. 验证并创建文档（如果不存在）
                doc_check_query = """
                    SELECT d.id, d.knowledge_base_id, kb.user_id
                    FROM chunk_schema.documents d
                    JOIN chunk_schema.knowledge_bases kb ON d.knowledge_base_id = kb.id
                    WHERE d.id = $1 AND d.knowledge_base_id = $2 AND kb.user_id = $3
                """
                doc_result = await conn.fetchrow(doc_check_query, document_id, knowledge_base_id, user_id)

                if not doc_result:
                    logger.info(f"Document {document_id} not found in knowledge base {knowledge_base_id}, creating new document")
                    doc_insert_query = """
                        INSERT INTO chunk_schema.documents (id, knowledge_base_id, name, text, component_ids, hierarchy_path)
                        VALUES ($1, $2, $3, $4, '{}', 'root'::ltree)
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(doc_insert_query, document_id, knowledge_base_id,
                                     document_name, "")
                    logger.info(f"Successfully created document {document_id}")

                # 4. 插入文本块到chunks表
                # 处理embedding向量格式 - 转换为pgvector兼容格式
                embedding_vector = None
                if embedding is not None:
                    # 验证embedding是否为有效的数字列表
                    if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
                        raise ValueError("Embedding must be a list of numbers")
                    if len(embedding) == 0:
                        raise ValueError("Embedding cannot be empty")
                    # 将Python列表转换为PostgreSQL数组格式，然后转换为vector类型
                    embedding_vector = f"[{','.join(map(str, embedding))}]"
                    logger.debug(f"Converted embedding to pgvector format: {embedding_vector[:100]}... (length: {len(embedding)})")

                insert_query = """
                    INSERT INTO chunk_schema.chunks
                    (id, document_id, doc_position, text, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    RETURNING id, doc_position
                """

                # 执行插入操作到chunks表
                # 触发器会自动同步到components表并处理所有相关更新
                result = await conn.fetchrow(
                    insert_query,
                    chunk_id,
                    document_id,
                    doc_position,
                    text,
                    embedding_vector
                )

                inserted_id = result['id']
                assigned_position = result['doc_position']

                logger.info(f"Successfully saved text chunk to database - "
                          f"chunk_id: {inserted_id}, document_id: {document_id}, "
                          f"position: {assigned_position}, "
                          f"text_length: {len(text)}")

                return inserted_id

        finally:
            await conn.close()

    except asyncpg.exceptions.UniqueViolationError as e:
        logger.error(f"Unique constraint violation when saving text chunk: {e}")
        raise ValueError(f"Chunk with ID {chunk_id} already exists")
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logger.error(f"Foreign key constraint violation when saving text chunk: {e}")
        raise ValueError(f"Invalid document_id: {document_id}")
    except Exception as e:
        logger.error(f"Failed to save text chunk to database: {e}")
        raise Exception(f"Database operation failed: {str(e)}")

# 将一个图片存入指定用户的指定知识库的指定文档的图片表
async def save_photo_to_vcdb_photo_table(
    photo_url: str,
    user_id: str,
    knowledge_base_id: str,
    document_id: str,
    document_name: str,
    position: int,
    text: str,
    photo_id: Optional[str] = None,
    photo_type: str = "photo",
    base64_image: Optional[str] = None,
    embedding: Optional[List[float]] = None
) -> str:
    """
    保存图片到chunk_schema.photos表的基础函数

    该函数将图片信息插入到photos表，触发器会自动：
    1. 同步数据到components表 (sync_photos_to_components)
    2. 确保doc_position唯一性 (ensure_doc_position_uniqueness)
    3. 更新全文搜索索引 (update_component_tsv)
    4. 更新文档内容和组件ID数组 (update_document_content, update_component_document_ids)

    验证逻辑：
    - 验证用户是否存在，不存在则创建
    - 验证知识库是否存在，不存在则创建
    - 验证文档是否存在，不存在则创建
    - 不验证或修改position参数，假设调用者提供正确的位置

    Args:
        photo_url: 图片URL
        user_id: 用户ID (用于上下文和验证)
        knowledge_base_id: 知识库ID (用于上下文和验证)
        document_id: 文档ID (外键引用)
        position: 文档中的位置（由调用者提供，不进行验证）
        text: 图片的描述文本
        photo_id: 图片ID，如果为None则自动生成UUID
        photo_type: 图片类型，默认为"photo"，可选"table"
        base64_image: 图片的base64编码，可选
        embedding: 向量嵌入，如果为None则不设置

    Returns:
        str: 插入的图片ID

    Raises:
        ValueError: 参数验证失败
        Exception: 数据库操作失败
    """
    # 参数验证
    if not photo_url:
        raise ValueError("photo_url is required")
    if not user_id:
        raise ValueError("user_id is required")
    if not knowledge_base_id:
        raise ValueError("knowledge_base_id is required")
    if not document_id:
        raise ValueError("document_id is required")
    if not isinstance(position, int) or position < 0:
        raise ValueError("position must be a non-negative integer")
    if not text:
        raise ValueError("text description is required")
    if photo_type not in ["photo", "table"]:
        raise ValueError("photo_type must be 'photo' or 'table'")

    # 生成图片ID（如果未提供）
    if photo_id is None:
        photo_id = str(uuid.uuid4())

    # 获取数据库配置
    pg_config = config["server_components"]["pg_vector"]

    try:
        # 建立数据库连接
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=int(pg_config["port"]),
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )

        try:
            async with conn.transaction():
                # 1. 验证并创建用户（如果不存在）
                user_check_query = "SELECT id FROM chunk_schema.users WHERE id = $1"
                user_result = await conn.fetchrow(user_check_query, user_id)

                if not user_result:
                    logger.info(f"User {user_id} not found, creating new user")
                    user_insert_query = """
                        INSERT INTO chunk_schema.users (id, knowledge_ids)
                        VALUES ($1, '{}')
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(user_insert_query, user_id)
                    logger.info(f"Successfully created user {user_id}")

                # 2. 验证并创建知识库（如果不存在）
                kb_check_query = """
                    SELECT id FROM chunk_schema.knowledge_bases
                    WHERE id = $1 AND user_id = $2
                """
                kb_result = await conn.fetchrow(kb_check_query, knowledge_base_id, user_id)

                if not kb_result:
                    logger.info(f"Knowledge base {knowledge_base_id} not found for user {user_id}, creating new knowledge base")
                    kb_insert_query = """
                        INSERT INTO chunk_schema.knowledge_bases (id, user_id, name, description, document_ids)
                        VALUES ($1, $2, $3, $4, '{}')
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(kb_insert_query, knowledge_base_id, user_id,
                                     f"Knowledge Base {knowledge_base_id}",
                                     f"Auto-created knowledge base for user {user_id}")
                    logger.info(f"Successfully created knowledge base {knowledge_base_id}")

                # 3. 验证并创建文档（如果不存在）
                doc_check_query = """
                    SELECT d.id, d.knowledge_base_id, kb.user_id
                    FROM chunk_schema.documents d
                    JOIN chunk_schema.knowledge_bases kb ON d.knowledge_base_id = kb.id
                    WHERE d.id = $1 AND d.knowledge_base_id = $2 AND kb.user_id = $3
                """
                doc_result = await conn.fetchrow(doc_check_query, document_id, knowledge_base_id, user_id)

                if not doc_result:
                    logger.info(f"Document {document_id} not found in knowledge base {knowledge_base_id}, creating new document")
                    doc_insert_query = """
                        INSERT INTO chunk_schema.documents (id, knowledge_base_id, name, text, component_ids, hierarchy_path)
                        VALUES ($1, $2, $3, $4, '{}', 'root'::ltree)
                        ON CONFLICT (id) DO NOTHING
                    """
                    await conn.execute(doc_insert_query, document_id, knowledge_base_id,
                                     document_name, "")
                    logger.info(f"Successfully created document {document_id}")

                # 4. 插入图片到photos表
                # 处理embedding向量格式 - 转换为pgvector兼容格式
                embedding_vector = None
                if embedding is not None:
                    # 验证embedding是否为有效的数字列表
                    if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
                        raise ValueError("Embedding must be a list of numbers")
                    if len(embedding) == 0:
                        raise ValueError("Embedding cannot be empty")
                    # 将Python列表转换为PostgreSQL数组格式，然后转换为vector类型
                    embedding_vector = f"[{','.join(map(str, embedding))}]"
                    logger.debug(f"Converted photo embedding to pgvector format: {embedding_vector[:100]}... (length: {len(embedding)})")

                insert_query = """
                    INSERT INTO chunk_schema.photos
                    (id, document_id, type, text, base64_image, embedding, doc_position)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
                    RETURNING id, doc_position
                """

                # 执行插入操作到photos表
                # 触发器会自动同步到components表并处理所有相关更新
                result = await conn.fetchrow(
                    insert_query,
                    photo_id,
                    document_id,
                    photo_type,
                    text,
                    base64_image,
                    embedding_vector,
                    position
                )

                inserted_id = result['id']
                assigned_position = result['doc_position']

                logger.info(f"Successfully saved photo to database - "
                          f"photo_id: {inserted_id}, document_id: {document_id}, "
                          f"position: {assigned_position}, "
                          f"photo_url: {photo_url}, "
                          f"text_length: {len(text)}")

                return inserted_id

        finally:
            await conn.close()

    except asyncpg.exceptions.UniqueViolationError as e:
        logger.error(f"Unique constraint violation when saving photo: {e}")
        raise ValueError(f"Photo with ID {photo_id} already exists")
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logger.error(f"Foreign key constraint violation when saving photo: {e}")
        raise ValueError(f"Invalid document_id: {document_id}")
    except Exception as e:
        logger.error(f"Failed to save photo to database: {e}")
        raise Exception(f"Database operation failed: {str(e)}")

async def save_something_to_vcdb(user_id:str,knowledge_base_id:str,document_id:str,document_name:str,position:int,text:str,type:str,embedding:List[float]):
    if type == "text":
        return await save_text_to_vcdb_text_table(text,document_id,document_name,user_id,knowledge_base_id,doc_position=position,embedding=embedding)
    elif type == "image":
        photo_url = extract_photo_url(text)
        return await save_photo_to_vcdb_photo_table(photo_url=photo_url,user_id=user_id,knowledge_base_id=knowledge_base_id,document_id=document_id,document_name=document_name,position=position,text=text,embedding=embedding)
    else:
        raise ValueError(f"Invalid type: {type}")

# 将json文件做嵌入，存入向量数据库
async def embedding_json_file(file_path:str,alias:str = "bge-m3"):
    # 读取json文件
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        results_dict = json.loads(await f.read())

    # 读取信号量配置，默认为1（串行），>1 时并发
    concurrency_limit = config.get("embedding_settings", {}).get("semaphore")
    if not concurrency_limit or concurrency_limit <= 0:
        concurrency_limit = 1
    logger.info(f"embedding_json_file 并发信号量设置为: {concurrency_limit}")
    sem = asyncio.Semaphore(concurrency_limit)

    new_results_dict = []

    # 配置更宽松的HTTP客户端以避免LocalProtocolError
    timeout = httpx.Timeout(
        connect=30.0,  # 连接超时
        read=60.0,     # 读取超时
        write=30.0,    # 写入超时
        pool=30.0      # 连接池超时
    )

    limits = httpx.Limits(
        max_keepalive_connections=20,  # 减少保持连接数
        max_connections=100,           # 减少最大连接数
        keepalive_expiry=30.0
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        http2=False,  # 禁用HTTP/2以避免协议问题
        verify=False  # 禁用SSL验证
    ) as shared_client:
        async def _embed(result: dict):
            async with sem:
                return await embedding_text(result["content"], result["index"], result["type"], alias, client=shared_client)

        tasks = [_embed(result) for result in results_dict]
        results = await asyncio.gather(*tasks)

    for index,embedding,text,type in results:
        new_results_dict.append({
            "index": index,
            "content": text,
            "type": type,
            "embedding": embedding
        })
    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(new_results_dict, ensure_ascii=False, indent=2))
    logger.info(f"将json文件中的全部类目全部条目embedding做嵌入完成，共{len(new_results_dict)}个条目，文件路径: {file_path}")
    # 返回文件路径
    return file_path
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, httpx.ProtocolError))
)
async def embedding_text(text: str,index:int,type:str,alias:str = "",client: Optional[httpx.AsyncClient] = None):
    # 使用singleton_embedding.py中的embedding_text函数
    if not alias:
        mode = "language_embedding"
        name,url,key,alias = get_latest_embedding_instance(instance_type=mode)
    else:
        name,url,key,alias = get_latest_embedding_instance(alias=alias)

    try:
        # 准备请求头 - 只有当key不为空时才添加Authorization header
        headers = {}
        if key and key.strip():
            headers["Authorization"] = f"Bearer {key}"

        # 复用传入的client，否则自行创建
        if client is None:
            # 配置更宽松的HTTP客户端
            timeout = httpx.Timeout(
                connect=30.0,
                read=60.0,
                write=30.0,
                pool=30.0
            )
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=50,
                keepalive_expiry=30.0
            )
            async with httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=False,
                verify=False
            ) as _client:
                response = await _client.post(url, headers=headers, json={"model": name, "input": text})
        else:
            response = await client.post(url, headers=headers, json={"model": name, "input": text})

        response.raise_for_status()  # 自动处理HTTP错误，确保HTTP错误触发重试机制
        embedding = response.json()
        return index,embedding["data"][0]["embedding"],text,type
    except Exception as e:
        logger.error(f"Embedding请求失败: {str(e)}, URL: {url}, 错误类型: {type(e).__name__}")
        raise

async def embedding_photo(photo_url:str,index:int,alias:str = ""):
    if not alias:
        mode = "multimodal_llm"
        name,url,key,alias = get_latest_embedding_instance(instance_type=mode)
    else:
        name,url,key,alias = get_latest_embedding_instance(alias=alias)
    if not photo_url:
        return None
    if not photo_url.startswith("http"):
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        # 使用正则表达式匹配图片url,必定是单个url
        matches = re.search(pattern, photo_url)
        if matches:
            photo_url = matches.group(2)
        else:
            return None
    description = await describe_photo(photo_url,index,alias)
    if not description:
        return None
    return index,description,photo_url

async def embedding_all_text(text: str,alias:str):
    #加入了分块策略
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'

    # text_list和image_list的元素均为元组，元组第一个元素为alltext中的"分块的块索引"，元组第二个元素为text或图片的![]()内容
    text_list = re.split(pattern, text)
    image_list = []
    # 找到所有匹配项及其位置
    matches = []
    for match in re.finditer(pattern, text):
        matches.append({
            'full_match': match.group(0),  # 完整匹配 ![nnnn](yuguyg.png)
            'alt_text': match.group(1),    # 替代文本 nnnn
            'image_path': match.group(2),  # 图片路径 yuguyg.png
            'start': match.start(),        # 开始位置
            'end': match.end()            # 结束位置
        })

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
async def download_file(file_url: str, file_path: str):
    # 增加一次兜底机会：如果第一次请求使用公网前缀失败，则转换为内网地址再试一次

    # 保留最初的 URL，用于判断前缀
    original_url = file_url

    # 封装一次真正执行 HTTP 下载的内部函数，避免代码重复
    async def _do_request(target_url: str):
        """执行一次真实的 HTTP 下载"""
        # 检查URL是否有效
        if not target_url or not target_url.startswith(('http://', 'https://')):
            logger.error(f"无效的文件URL: {target_url}")
            raise ValueError(f"无效的文件URL: {target_url}")

        try:
            logger.info(f"开始下载文件: {target_url} 到 {file_path}")

            # 增强的HTTP客户端配置
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # 配置更宽松的超时和限制
            timeout = httpx.Timeout(
                connect=30.0,  # 连接超时
                read=120.0,    # 读取超时
                write=30.0,    # 写入超时
                pool=30.0      # 连接池超时
            )

            # 配置更宽松的限制
            limits = httpx.Limits(
                max_keepalive_connections=50,
                max_connections=300,
                keepalive_expiry=30.0
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                headers=headers,
                follow_redirects=True,
                verify=False  # 暂时禁用SSL验证以排除证书问题
            ) as client:

                # 先进行HEAD请求检查文件是否存在
                try:
                    logger.info(f"检查文件可访问性: {target_url}")
                    head_response = await client.head(target_url)
                    logger.info(f"HEAD请求成功: {head_response.status_code}, Content-Length: {head_response.headers.get('content-length', 'unknown')}")
                except Exception as head_error:
                    logger.warning(f"HEAD请求失败，继续尝试GET请求: {head_error}")

                # 执行GET请求下载文件
                logger.info(f"开始GET请求下载文件: {target_url}")
                response = await client.get(target_url)

                # 详细记录响应信息
                logger.info(f"GET响应状态: {response.status_code}")
                logger.info(f"响应头: {dict(response.headers)}")

                response.raise_for_status()

                # 检查响应内容是否为空
                if not response.content:
                    logger.error(f"下载的文件内容为空: {target_url}")
                    raise ValueError(f"下载的文件内容为空: {target_url}")

                # 确保目标目录存在
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(response.content)

                logger.info(f"文件下载成功: {file_path}, 大小: {len(response.content)} 字节")
                return file_path

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP状态错误: {e.response.status_code} - {e.response.reason_phrase}")
            logger.error(f"响应头: {dict(e.response.headers)}")
            logger.error(f"响应内容: {e.response.text[:500]}...")  # 只记录前500字符
            logger.error(f"请求URL: {target_url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"请求错误: {str(e)}, URL: {target_url}")
            logger.error(f"错误类型: {type(e).__name__}")
            raise
        except Exception as e:
            logger.error(f"下载文件时发生未预期的错误: {str(e)}, URL: {target_url}")
            logger.error(f"错误类型: {type(e).__name__}")
            raise Exception(f"下载文件失败: {str(e)}")

    # ---------- 主逻辑 ----------
    try:
        return await _do_request(file_url)
    except Exception as first_error:
        # 如果失败且符合公网前缀，则尝试内网 URL 一次
        internal_url = convert_to_internal_minio_url(original_url)
        if internal_url != original_url:
            logger.warning(f"首次下载失败，将公网 URL 切换为内网地址重试: {internal_url}")
            try:
                return await _do_request(internal_url)
            except Exception as second_error:
                logger.error("使用内网地址兜底下载仍然失败")
                # 将第一次异常链保留以便排查
                raise second_error from first_error
        # 若前缀不匹配或其他原因，直接抛出第一次异常
        raise first_error

async def request_mineru(file_url: str):
    # 请求mineru，返回存储的md的url
    
    pass

async def mineru_process(file_url: str, knowledge_base_id: str, mode: str, user_id: str,raw_file_url_to_return:str = ""):
    tmp_dir = Path(__file__).parent / "tmp"
    # 确保tmp目录存在
    file_uuid = str(uuid.uuid4())
    os.makedirs(tmp_dir, exist_ok=True)
    ocr_file_path = tmp_dir / f"{file_uuid}_ocr.md"
    # 下载文件到本地
    logger.info(f"----------------第一阶段：下载文件------------------")
    logger.info(f"收到请求：user_id: {user_id}, file_url: {file_url}, knowledge_base_id: {knowledge_base_id}, mode: {mode}, ")
    file_name = file_url.split('/')[-1]
    file_path = tmp_dir / f"{file_uuid}.{file_url.split('.')[-1]}"
    logger.info(f"开始下载文件到本地: {file_path}")
    await download_file(file_url, file_path)
    logger.info(f"下载文件到本地完成: {file_path}")
    file_url_str = str(file_path)
    raw_file_name = file_name
    # 使用pdfplumber读取pdf文件
    logger.info(f"----------------第二阶段：读取文本------------------")
    if mode == "simple":
        text = await plumber_read_pdf(file_url_str)
        logger.info(f"使用simple模式读取pdf文件完成，共{len(text)}个字符")
        if text == "" or not text:
            text = "这是一个占位符，用于保证边缘情况，需要图片处理走normal模式"
            logger.info(f"原文件为图片或仅含图片的文档格式，已使用占位符填充保证边缘情况，需要图片处理走normal模式")
    elif mode == "normal":
        ocr_url = await request_mineru(file_url)
        await download_file(ocr_url, ocr_file_path)
        logger.info(f"下载文件到本地完成: {ocr_file_path}")
        # 读取md文件
        async with aiofiles.open(ocr_file_path, "r", encoding="utf-8") as f:
            text = await f.read()
        logger.info(f"读取md文件完成，共{len(text)}个字符")
        if not text or text == "":
            text = "这是一个占位符，用于保证边缘情况,文档已经mineru处理"
            logger.info(f"已经过mineru处理，但text为空，已使用占位符填充保证边缘情况，可能是文档为空文档")
    else:
        raise ValueError(f"Invalid mode: {mode}")
    logger.info(f"------------------第三阶段：前处理--------------------")
    # 进行两轮分块策略，第一轮以图片为间隔，第二轮针对文本进行分块
    # 第一轮分块策略
    # 将文本进行图片链接替换和分块为列表，列表的元素为(开始索引, 结束索引, 类型)
    logger.info(f"开始进行第一轮图片边界分块策略，开始分块")
    text,results = await asyncio.to_thread(find_all_text_and_image_index,text,user_id,knowledge_base_id,file_uuid)
    logger.info(f"第一轮以图片为分界，分块策略完成，共{len(results)}个条目")
    # 保存results到json文件，转换后的json除了uuid，_convertedurl.json结尾
    # 构建JSON文件路径: uuid_convertedurl.json (避免重复UUID)
    json_file_path = file_path.parent / f"{file_uuid}_convertedurl.json"
    # 保存初次结果为json文件
    await save_results_to_json(text, results, str(json_file_path))
    logger.info(f"保存初次结果为json文件成功，已将图片描述文本替换到[]里，文件路径: {json_file_path}")
    logger.info("开始进行第二轮文本分块策略，开始分块")
    # 第二轮分块策略
    # 将json文件中的文本进行分块策略 
    await split_text_by_json(str(json_file_path))
    logger.info(f"第二轮将类型为text的文本进行分块策略完成，共{len(results)}个条目")
    # 将json文件中的embedding做嵌入
    logger.info("开始进行第三轮embedding策略，开始embedding")
    json_file_path = await embedding_json_file(str(json_file_path))
    logger.info(f"将json文件中的全部类目全部条目embedding做嵌入完成，共{len(results)}个条目，文件路径: {json_file_path}")
    logger.info("----------------第四阶段：存入向量数据库------------------")
    # 将json文件中的全部类目全部条目存入向量数据库
    async with aiofiles.open(json_file_path, "r", encoding="utf-8") as f:
        results = json.loads(await f.read())
    tasks = [save_something_to_vcdb(user_id,knowledge_base_id,file_uuid,raw_file_name,result["index"],result["content"],result["type"],result["embedding"]) for result in results]
    await asyncio.gather(*tasks)
    logger.info("将json文件中的全部类目全部条目存入向量数据库完成，共{len(results)}个条目")
    logger.info("----------------第五阶段：做云端存储------------------")
    logger.info("----------半处理json解析为md文件,存储md用于预览---------")
    logger.info("-----------------全处理json, 存储json-----------------")   
    # 写入md文件
    async with aiofiles.open(file_path.with_suffix(".md"), "w", encoding="utf-8") as f:
        await f.write(text)
    try:
        # 使用miniosdk上传md文件到minio，minio相关配置在config.yaml中
        host = config["server_components"]["minio"]["host"]
        port = int(config["server_components"]["minio"]["port"])
        access_key = config["server_components"]["minio"]["access_key"]
        secret_key = config["server_components"]["minio"]["secret_key"]
        region = config["server_components"]["minio"]["region"]
        bucket_name = config["server_components"]["minio"]["bucket_name"]
        # MinIO client endpoint should be "host:port" and secure=False for HTTP
        endpoint = f"{host}:{port}"
        minio_client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False, region=region)
        # 检测 MIME 类型
        md_content_type = detect_content_type(str(file_path.with_suffix(".md")))
        pdf_content_type = detect_content_type(str(file_path))

        # 上传 MD 文件
        await asyncio.to_thread(
            minio_client.fput_object,
            bucket_name,
            f"{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.md",
            str(file_path.with_suffix(".md")),
            md_content_type
        )
        # 上传 PDF 文件
        await asyncio.to_thread(
            minio_client.fput_object,
            bucket_name,
            f"{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.pdf",
            str(file_path),
            pdf_content_type
        )
        md_file_public_url = f"{config['server_components']['minio']['public_url_prefix']}/{bucket_name}/{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.md"
        pdf_file_public_url = f"{config['server_components']['minio']['public_url_prefix']}/{bucket_name}/{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.pdf"
        pg_config = config["server_components"]["pg_vector"]
        conn = await asyncpg.connect(
        host=pg_config["host"],
        port=int(pg_config["port"]),
        user=pg_config["user"],
        password=pg_config["password"],
        database=pg_config["database"]
    )
        async with conn.transaction():
            await conn.execute(f"""UPDATE chunk_schema.documents SET markdown_public_url = '{md_file_public_url}', raw_file_public_url = '{raw_file_url_to_return}', name = '{raw_file_name}', upload_time = now() WHERE id = '{file_uuid}'""")
        logger.info(f"用户{user_id}上传md文件到minio成功: {md_file_public_url},且将源文件的pdf格式上传到minio成功: {pdf_file_public_url},且更新数据库成功")

        # 返回md文件的公网url
        return {"markdown_public_url": f"{config['server_components']['minio']['public_url_prefix']}/{bucket_name}/{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.md",
            "pdf_file_public_url": f"{config['server_components']['minio']['public_url_prefix']}/{bucket_name}/{user_id}/knowledgebase/{knowledge_base_id}/{file_uuid}/{file_uuid}.pdf",
            "file_uuid": file_uuid
            }

    except Exception as e:
        logger.error(f"上传md文件到minio失败: {e}")
        return None
    finally:
        # 删除本地文件，pdf和md文件，json文件
        await asyncio.to_thread(Path(file_path).unlink, missing_ok=True)
        await asyncio.to_thread(Path(file_path.with_suffix(".md")).unlink, missing_ok=True)
        await asyncio.to_thread(Path(json_file_path).unlink, missing_ok=True)
        await asyncio.to_thread(Path(ocr_file_path).unlink, missing_ok=True)
        # 关闭数据库连接
        await conn.close()
        logger.info(f"删除本地文件: {file_path} 和 {file_path.with_suffix('.md')} 和 {json_file_path}")
       

async def test_download_file(file_url: str):
    """
    测试文件下载功能的独立函数
    """
    import tempfile
    import os

    try:
        # 创建临时文件路径
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            temp_path = tmp_file.name

        logger.info(f"测试下载文件: {file_url}")
        result = await download_file(file_url, temp_path)
        logger.info(f"下载测试成功: {result}")

        # 检查文件是否存在和大小
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            logger.info(f"下载的文件大小: {file_size} 字节")

            # 清理临时文件
            os.unlink(temp_path)
            return True
        else:
            logger.error("下载的文件不存在")
            return False

    except Exception as e:
        logger.error(f"下载测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 可以用于测试下载功能
    # asyncio.run(test_download_file("http://example.com/test.pdf"))
    asyncio.run(mineru_process("http://1.tcp.cpolar.cn:21729/publicfiles/xx.pdf", "xxx", "simple", "e4f7d0a3-fa32-4ca6-964e-01d02104844b"))






