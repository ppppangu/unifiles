import httpx
import asyncio
import json
import re
import asyncpg
import jinja2
from loguru import logger
from src.tools import (
    read_config,
    read_pg_config,
)
from jsonschema import validate, ValidationError
from singleton_embedding import get_latest_embedding_instance
# 导入重试装饰器
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 初始化配置
config = read_config()
pg_config = read_pg_config()

# 模块级别日志
logger.info("Graph module initialized")

extract_info_template = jinja2.Template("""
{% if knowledge_base_structure %}
知识库的已有逻辑结构：
{{ knowledge_base_structure }}

该文档在该知识库中的逻辑位置：
{{ document_location }}

{% endif %}
                                        
{% if user_info %}
用户的一些额外相关信息：
{{ user_info }}
{% endif %}

{% if text %}
要总结的文档内容：
{{ text }}
{% endif %}

请根据所给信息，生成对应文档的tags标签列表，最多生成6个标签，最少生成1个标签。
tags标签需要用`json`格式返回，格式如下：
```json
[
    "tag1",
    "tag2",
    "tag3"
]
""")

tags_schema = {
    "type": "array",
    "items": {
        "type": "string"
    }
}

def tags_validate(tags: list[str])->bool:
    """验证tags标签列表是否符合要求"""
    try:
        validate(instance=tags, schema=tags_schema)
        logger.debug(f"Tags validation successful: {tags}")
        return True
    except ValidationError as e:
        logger.warning(f"Tags validation failed: {tags}, error: {e}")
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15), retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError)))
async def extract_summary(text: str, knowledge_base_structure: str = "", user_info: str = "", document_location: str = "")->list[str]:
    """根据知识库文档内容,知识库逻辑结构,用户的一些额外相关信息，生成这个文档的tags标签列表"""
    logger.info(f"Starting extract_summary - text_length: {len(text)}, has_kb_structure: {bool(knowledge_base_structure)}, has_user_info: {bool(user_info)}, document_location: {document_location}")

    prompt = extract_info_template.render(knowledge_base_structure=knowledge_base_structure, user_info=user_info, text=text, document_location=document_location)
    logger.debug(f"Generated prompt length: {len(prompt)}")

    # 获取语言模型实例
    try:
        language_llm_instance = get_latest_embedding_instance(instance_type="language_llm")
        # 获取语言模型实例的name,url,key,alias
        language_llm_name, language_llm_url, language_llm_key, language_llm_alias = language_llm_instance
        logger.info(f"Using language model: {language_llm_name} at {language_llm_url}")
    except Exception as e:
        logger.error(f"Failed to get language model instance: {e}")
        raise

    async with httpx.AsyncClient(timeout=30) as client:
        logger.debug(f"Making API request to {language_llm_url}")
        response = await client.post(
            url=language_llm_url,
            headers={"Authorization": f"Bearer {language_llm_key}"},
            json={"model": language_llm_name, "messages": [{"role": "user", "content": prompt}],"stream": False})

        logger.info(f"API response status: {response.status_code}")
        if response.status_code == 200:
            response_data = response.json()
            tags = response_data["choices"][0]["message"]["content"]
            logger.debug(f"Raw LLM response: {tags[:200]}...")

            pattern = r"```json\n(.*?)\n```"
            match = re.search(pattern, tags, re.DOTALL)
            if not match:
                logger.error(f"Failed to extract JSON from LLM response: {tags}")
                raise ValueError("No JSON found in LLM response")

            tags_json = match.group(1)
            logger.debug(f"Extracted JSON: {tags_json}")

            try:
                tags = json.loads(tags_json)
                logger.debug(f"Parsed tags: {tags}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {tags_json}, error: {e}")
                raise ValueError(f"Invalid JSON in LLM response: {e}")

            if tags_validate(tags):
                logger.info(f"Successfully extracted {len(tags)} tags")
                return {"status": "ok", "tags": tags}
            else:
                logger.error(f"Tags validation failed: {tags}")
                raise ValueError("Tags is not valid")
        else:
            logger.error(f"Language model API error: {response.status_code}, response: {response.text}")
            raise ValueError(f"Language model response error: {response.status_code}")
        
async def single_document_summary(
    text: str,
    knowledge_base_structure: str = "",
    user_info: str = "",
    document_location: str = "",
    window_size: int = 30000,
) -> list[str]:
    """对单个文档文本进行tags抽取。若文本为空直接返回空列表。"""
    logger.debug(f"Starting single_document_summary - text_length: {len(text) if text else 0}, window_size: {window_size}, document_location: {document_location}")

    if not text:
        logger.debug("Text is empty, returning empty list")
        return []

    # 截取指定窗口大小的文本
    truncated_text = text[:window_size]
    if len(text) > window_size:
        logger.info(f"Text truncated from {len(text)} to {window_size} characters")

    try:
        logger.debug("Calling extract_summary")
        result = await extract_summary(
            truncated_text,
            knowledge_base_structure=knowledge_base_structure,
            user_info=user_info,
            document_location=document_location,
        )
        if result["status"] == "ok":
            tags = result["tags"]
            logger.info(f"Successfully extracted {len(tags)} tags: {tags}")
            return tags
        else:
            logger.warning(f"extract_summary returned non-ok status: {result}")
    except Exception as e:
        logger.error(f"single_document_summary error: {e}", exc_info=True)

    logger.debug("Returning empty list due to error or failure")
    return []

async def database_validate(user_id: str, knowledge_base_id: str)->list[dict]:
    """校验用户,知识库是否存在,如果存在,返回知识库下文档列表"""
    logger.info(f"Starting database_validate - user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")

    try:
        logger.debug(f"Connecting to database: {pg_config['host']}:{pg_config['port']}")
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )
        logger.debug("Database connection established")

        async with conn.transaction():
            # 校验用户存在
            user_exist_query = f"""SELECT * FROM zhida_users WHERE uuid = '{user_id}'"""
            logger.debug(f"Executing user validation query: {user_exist_query}")
            user_exist_result = await conn.fetch(user_exist_query)
            logger.info(f"User validation result: {len(user_exist_result)} records found")

            if len(user_exist_result) == 0:
                logger.warning(f"User {user_id} not found in zhida_users table")
                return {"status": "error", "message": "User not found"}

            # 校验知识库存在
            knowledge_base_exist_query = f"""SELECT * FROM chunk_schema.knowledge_bases WHERE uuid = '{knowledge_base_id}'"""
            logger.debug(f"Executing knowledge base validation query: {knowledge_base_exist_query}")
            knowledge_base_exist_result = await conn.fetch(knowledge_base_exist_query)
            logger.info(f"Knowledge base validation result: {len(knowledge_base_exist_result)} records found")

            if len(knowledge_base_exist_result) == 0:
                logger.warning(f"Knowledge base {knowledge_base_id} not found in chunk_schema.knowledge_bases table")
                return {"status": "error", "message": "Knowledge base not found"}

            # 获取知识库下文档列表
            document_list_query = f"""SELECT * FROM chunk_schema.documents WHERE knowledge_base_id = '{knowledge_base_id}'"""
            logger.debug(f"Executing document list query: {document_list_query}")
            document_list_result = await conn.fetch(document_list_query)
            logger.info(f"Document list result: {len(document_list_result)} documents found")

            if len(document_list_result) == 0:
                logger.warning(f"No documents found in knowledge base {knowledge_base_id}")
                return {"status": "error", "message": "Document list is empty,please upload documents first"}

            logger.info(f"Database validation successful - user: {user_id}, kb: {knowledge_base_id}, docs: {len(document_list_result)}")
            return {"status": "ok", "document_list": document_list_result}

    except Exception as e:
        logger.error(f"Database validation error: {e}", exc_info=True)
        return {"status": "error", "message": "Database validate error"}
    finally:
        if 'conn' in locals():
            await conn.close()
            logger.debug("Database connection closed")


async def produce_summary_task(user_id: str, knowledge_base_id: str, document_id: str):
    """生成总结任务(当前未使用, 仅保留示例以避免语法错误)"""
    logger.warning(f"produce_summary_task called with deprecated function - user_id: {user_id}, kb: {knowledge_base_id}, doc: {document_id}")
    try:
        # 这里只是占位实现, 实际业务请使用produce_document_graph
        return {"status": "ok", "message": "Task is deprecated, please use produce_document_graph"}
    except Exception as e:
        logger.error(f"produce_summary_task error: {e}")
        return {"status": "error", "message": str(e)}

async def get_user_info(user_id: str) -> str:
    """获取用户的一些额外相关信息"""
    logger.debug(f"Getting user info for user: {user_id}")
    # 目前返回空字符串，未来可以扩展获取用户相关信息
    return ""

async def produce_document_graph(user_id: str, knowledge_base_id: str):
    """批量为 knowledge_base_id 下的所有文档生成 tags, 并写回 documents.tags 列"""
    logger.info(f"Starting produce_document_graph - user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")

    window_size = (
        config.get("graph_module", {})
        .get("summary_strategy", {})
        .get("window_size", 30000)
    )
    logger.info(f"Using window_size: {window_size}")

    try:
        logger.debug(f"Connecting to database: {pg_config['host']}:{pg_config['port']}")
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"],
        )
        logger.debug("Database connection established")

        async with conn.transaction():
            # 校验用户
            logger.debug(f"Validating user: {user_id}")
            user_row = await conn.fetchrow(
                "SELECT knowledge_ids FROM chunk_schema.users WHERE id = $1", user_id
            )
            if not user_row:
                logger.warning(f"User {user_id} not found in chunk_schema.users")
                return {"status": "error", "message": "User not found"}
            logger.debug(f"User validation successful: {user_id}")

            # 校验知识库
            logger.debug(f"Validating knowledge base: {knowledge_base_id} for user: {user_id}")
            kb_row = await conn.fetchrow(
                "SELECT id FROM chunk_schema.knowledge_bases WHERE id = $1 AND user_id = $2",
                knowledge_base_id,
                user_id,
            )
            if not kb_row:
                logger.warning(f"Knowledge base {knowledge_base_id} not found for user {user_id}")
                return {"status": "error", "message": "Knowledge base not found"}
            logger.debug(f"Knowledge base validation successful: {knowledge_base_id}")

            # 获取知识库内全部文档
            logger.debug(f"Fetching documents for knowledge base: {knowledge_base_id}")
            documents: list[asyncpg.Record] = await conn.fetch(
                "SELECT id, name, text, hierarchy_path, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            logger.info(f"Found {len(documents)} documents in knowledge base {knowledge_base_id}")

            if not documents:
                logger.warning(f"No documents found in knowledge base {knowledge_base_id}")
                return {
                    "status": "error",
                    "message": "Document list is empty, please upload documents first",
                }

            # 知识库整体结构
            logger.debug(f"Fetching hierarchy structure for knowledge base: {knowledge_base_id}")
            hierarchy_row = await conn.fetchrow(
                "SELECT labels FROM chunk_schema.logical_hierarchy WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            overall_structure = str(hierarchy_row["labels"]) if hierarchy_row and hierarchy_row["labels"] else ""
            logger.debug(f"Knowledge base structure: {overall_structure[:100]}..." if overall_structure else "No structure found")

            logger.debug(f"Getting user info for user: {user_id}")
            user_info = await get_user_info(user_id)

            # 并发生成 tags
            logger.info(f"Starting concurrent tag generation for {len(documents)} documents")
            tasks = []
            for i, doc in enumerate(documents):
                logger.debug(f"Creating task {i+1}/{len(documents)} for document: {doc['id']}")
                tasks.append(
                    single_document_summary(
                        text=doc["text"] or "",
                        knowledge_base_structure=overall_structure,
                        user_info=user_info,
                        document_location=str(doc["hierarchy_path"]) if doc["hierarchy_path"] else "",
                        window_size=window_size,
                    )
                )

            logger.info(f"Executing {len(tasks)} tag generation tasks concurrently")
            tags_list = await asyncio.gather(*tasks)
            logger.info(f"Completed tag generation for all documents")

            # 将 tags 写回数据库
            updated_count = 0
            for doc, tags in zip(documents, tags_list):
                if tags:
                    logger.debug(f"Updating tags for document {doc['id']}: {tags} (type: {type(tags)})")
                    await conn.execute(
                        "UPDATE chunk_schema.documents SET tags = $1 WHERE id = $2",
                        tags,
                        doc["id"],
                    )
                    updated_count += 1

                    # 验证更新是否成功 - 立即读回检查
                    verification = await conn.fetchrow(
                        "SELECT tags FROM chunk_schema.documents WHERE id = $1",
                        doc["id"]
                    )
                    logger.debug(f"Verification read for document {doc['id']}: {verification['tags']} (type: {type(verification['tags'])})")
                else:
                    logger.debug(f"No tags generated for document {doc['id']}")

            logger.info(f"Successfully updated tags for {updated_count}/{len(documents)} documents")
            return {"status": "ok", "message": "Tags generated successfully"}
    except Exception as e:
        logger.error(f"produce_document_graph error for user {user_id}, kb {knowledge_base_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        if "conn" in locals():
            await conn.close()
            logger.debug("Database connection closed")

async def get_documents_graph(user_id: str, knowledge_base_id: str):
    """获取 knowledge_base_id 下所有文档的基本信息(id, name, tags)"""
    logger.info(f"Starting get_documents_graph - user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")

    try:
        logger.debug(f"Connecting to database: {pg_config['host']}:{pg_config['port']}")
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"],
        )
        logger.debug("Database connection established")

        async with conn.transaction():
            # 校验用户
            logger.debug(f"Validating user: {user_id}")
            user_row = await conn.fetchrow(
                "SELECT 1 FROM chunk_schema.users WHERE id = $1", user_id
            )
            if not user_row:
                logger.warning(f"User {user_id} not found in chunk_schema.users")
                return {"status": "error", "message": "User not found"}
            logger.debug(f"User validation successful: {user_id}")

            # 校验知识库
            logger.debug(f"Validating knowledge base: {knowledge_base_id} for user: {user_id}")
            kb_row = await conn.fetchrow(
                "SELECT 1 FROM chunk_schema.knowledge_bases WHERE id = $1 AND user_id = $2",
                knowledge_base_id,
                user_id,
            )
            if not kb_row:
                logger.warning(f"Knowledge base {knowledge_base_id} not found for user {user_id}")
                return {"status": "error", "message": "Knowledge base not found"}
            logger.debug(f"Knowledge base validation successful: {knowledge_base_id}")

            # 获取文档列表 - 添加更详细的调试信息
            logger.debug(f"Fetching documents for knowledge base: {knowledge_base_id}")
            rows = await conn.fetch(
                "SELECT id, name, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            logger.info(f"Found {len(rows)} documents in knowledge base {knowledge_base_id}")

            documents = []
            for i, r in enumerate(rows):
                # 确保tags字段正确处理 - 处理可能的数据类型问题
                raw_tags = r["tags"]
                if raw_tags is None:
                    tags = []
                elif isinstance(raw_tags, list):
                    tags = raw_tags
                elif isinstance(raw_tags, str):
                    # 如果tags是字符串，尝试解析为JSON
                    try:
                        tags = json.loads(raw_tags) if raw_tags.strip() else []
                    except (json.JSONDecodeError, AttributeError):
                        logger.warning(f"Failed to parse tags as JSON for document {r['id']}: {raw_tags}")
                        tags = []
                else:
                    # 其他类型，尝试转换为列表
                    try:
                        tags = list(raw_tags)
                    except (TypeError, ValueError):
                        logger.warning(f"Unexpected tags type for document {r['id']}: {type(raw_tags)} - {raw_tags}")
                        tags = []

                doc = {"id": r["id"], "name": r["name"], "tags": tags}
                documents.append(doc)

                # 添加更详细的调试信息
                logger.debug(f"Document {i+1}/{len(rows)}: {doc['id']} - {doc['name']}")
                logger.debug(f"  Raw tags from DB: {raw_tags} (type: {type(raw_tags)})")
                logger.debug(f"  Processed tags: {tags} (type: {type(tags)}, length: {len(tags)})")

            logger.info(f"Successfully retrieved {len(documents)} documents for knowledge base {knowledge_base_id}")

            # 添加最终结果的调试信息
            for doc in documents:
                if doc["tags"]:
                    logger.info(f"Document {doc['id']} has {len(doc['tags'])} tags: {doc['tags']}")
                else:
                    logger.warning(f"Document {doc['id']} has no tags (empty or None)")

            return {"status": "ok", "documents": documents}

    except Exception as e:
        logger.error(f"get_documents_graph error for user {user_id}, kb {knowledge_base_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        if "conn" in locals():
            await conn.close()
            logger.debug("Database connection closed")

async def produce_subject_graph(user_id: str, knowledge_base_id: str):
    logger.info(f"produce_subject_graph called - user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")
    logger.warning("produce_subject_graph is not implemented yet")
    return {"status": "ok", "message": "Knowledge base request received"}

async def get_subject_graph(user_id: str, knowledge_base_id: str):
    logger.info(f"get_subject_graph called - user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")
    logger.warning("get_subject_graph is not implemented yet")
    return {"status": "ok", "message": "Knowledge base request received"}

if __name__ == "__main__":
    logger.info("Running graph_module as main script")
    asyncio.run(produce_document_graph("123", "456"))