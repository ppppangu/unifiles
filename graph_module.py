from cgitb import text
import httpx
import asyncio
import logging
import os
import json
import time
import random
import string
import traceback
import asyncpg
import yaml
import re
from loguru import logger
from src.tools import (
    read_config,
    read_pg_config,
    read_minio_config,
    mk_need_path
)
import jinja2
from jsonschema import validate, ValidationError
from singleton_embedding import get_latest_embedding_instance
# 导入重试装饰器
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

config = read_config()
pg_config = read_pg_config()

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

请根据所给信息，生成对应文档的tags标签列表。
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
        return True
    except ValidationError as e:
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15), retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError)))
async def extract_summary(text: str, knowledge_base_structure: str = "", user_info: str = "", document_location: str = "")->list[str]:
    """根据知识库文档内容,知识库逻辑结构,用户的一些额外相关信息，生成这个文档的tags标签列表"""
    prompt = extract_info_template.render(knowledge_base_structure=knowledge_base_structure, user_info=user_info, text=text, document_location=document_location)
    # 获取语言模型实例
    language_llm_instance = get_latest_embedding_instance(instance_type="language_llm")
    # 获取语言模型实例的url,key,alias
    language_llm_url, language_llm_key, language_llm_alias = language_llm_instance

    async with httpx.AsyncClient(base_url=language_llm_url, timeout=30) as client:
        response = await client.post(
            url="/v1/chat/completions",
            headers={"Authorization": f"Bearer {language_llm_key}"},
            json={"model": language_llm_alias, "messages": [{"role": "user", "content": prompt}],"stream": False})
        if response.status_code == 200:
            tags = response.json()["choices"][0]["message"]["content"]
            pattern = r"```json\n(.*?)\n```"
            tags = re.search(pattern, tags, re.DOTALL).group(1)
            tags = json.loads(tags)
            if tags_validate(tags):
                return {"status": "ok", "tags": tags}
            else:
                raise ValueError("Tags is not valid")
        else:
            raise ValueError("Language model response is not ok")
        
async def single_document_summary(
    text: str,
    knowledge_base_structure: str = "",
    user_info: str = "",
    document_location: str = "",
    window_size: int = 30000,
) -> list[str]:
    """对单个文档文本进行tags抽取。若文本为空直接返回空列表。"""
    if not text:
        return []
    # 截取指定窗口大小的文本
    truncated_text = text[:window_size]
    try:
        result = await extract_summary(
            truncated_text,
            knowledge_base_structure=knowledge_base_structure,
            user_info=user_info,
            document_location=document_location,
        )
        if result["status"] == "ok":
            return result["tags"]
    except Exception as e:
        logger.error(f"single_document_summary error: {e}")
    return []

async def database_validate(user_id: str, knowledge_base_id: str)->list[dict]:
    """校验用户,知识库是否存在,如果存在,返回知识库下文档列表"""
    try:
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )
        async with conn.transaction():
            # 校验用户存在
            user_exist_query = f"""SELECT * FROM zhida_users WHERE uuid = '{user_id}'"""
            user_exist_result = await conn.fetch(user_exist_query)
            if len(user_exist_result) == 0:
                return {"status": "error", "message": "User not found"}
            # 校验知识库存在
            knowledge_base_exist_query = f"""SELECT * FROM chunk_schema.knowledge_bases WHERE uuid = '{knowledge_base_id}'"""
            knowledge_base_exist_result = await conn.fetch(knowledge_base_exist_query)
            if len(knowledge_base_exist_result) == 0:
                return {"status": "error", "message": "Knowledge base not found"}
            # 获取知识库下文档列表
            document_list_query = f"""SELECT * FROM chunk_schema.documents WHERE knowledge_base_id = '{knowledge_base_id}'"""
            document_list_result = await conn.fetch(document_list_query)
            if len(document_list_result) == 0:
                return {"status": "error", "message": "Document list is empty,please upload documents first"}
            return {"status": "ok", "document_list": document_list_result}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error", "message": "Database validate error"}
    finally:
        await conn.close()


async def produce_summary_task(user_id: str, knowledge_base_id: str, document_id: str):
    """生成总结任务(当前未使用, 仅保留示例以避免语法错误)"""
    try:
        # 这里只是占位实现, 实际业务请使用produce_document_graph
        return {"status": "ok", "message": "Task is deprecated, please use produce_document_graph"}
    except Exception as e:
        logger.error(f"produce_summary_task error: {e}")
        return {"status": "error", "message": str(e)}

async def get_user_info(user_id: str) -> str:
    """获取用户的一些额外相关信息"""
    return ""

async def produce_document_graph(user_id: str, knowledge_base_id: str):
    """批量为 knowledge_base_id 下的所有文档生成 tags, 并写回 documents.tags 列"""
    window_size = (
        config.get("graph_module", {})
        .get("summary_strategy", {})
        .get("window_size", 30000)
    )

    try:
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"],
        )
        async with conn.transaction():
            # 校验用户
            user_row = await conn.fetchrow(
                "SELECT knowledge_ids FROM chunk_schema.users WHERE id = $1", user_id
            )
            if not user_row:
                return {"status": "error", "message": "User not found"}

            # 校验知识库
            kb_row = await conn.fetchrow(
                "SELECT id FROM chunk_schema.knowledge_bases WHERE id = $1 AND user_id = $2",
                knowledge_base_id,
                user_id,
            )
            if not kb_row:
                return {"status": "error", "message": "Knowledge base not found"}

            # 获取知识库内全部文档
            documents: list[asyncpg.Record] = await conn.fetch(
                "SELECT id, name, text, hierarchy_path, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            if not documents:
                return {
                    "status": "error",
                    "message": "Document list is empty, please upload documents first",
                }

            # 知识库整体结构
            hierarchy_row = await conn.fetchrow(
                "SELECT labels FROM chunk_schema.logical_hierarchy WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            overall_structure = str(hierarchy_row["labels"]) if hierarchy_row and hierarchy_row["labels"] else ""

            user_info = await get_user_info(user_id)

            # 并发生成 tags
            tasks = []
            for doc in documents:
                tasks.append(
                    single_document_summary(
                        text=doc["text"] or "",
                        knowledge_base_structure=overall_structure,
                        user_info=user_info,
                        document_location=str(doc["hierarchy_path"]) if doc["hierarchy_path"] else "",
                        window_size=window_size,
                    )
                )
            tags_list = await asyncio.gather(*tasks)

            # 将 tags 写回数据库
            for doc, tags in zip(documents, tags_list):
                if tags:
                    await conn.execute(
                        "UPDATE chunk_schema.documents SET tags = $1 WHERE id = $2",
                        tags,
                        doc["id"],
                    )

            return {"status": "ok", "message": "Tags generated successfully"}
    except Exception as e:
        logger.error(f"produce_document_graph error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if "conn" in locals():
            await conn.close()

async def get_documents_graph(user_id: str, knowledge_base_id: str):
    """获取 knowledge_base_id 下所有文档的基本信息(id, name, tags)"""
    try:
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"],
        )
        async with conn.transaction():
            # 校验用户
            user_row = await conn.fetchrow(
                "SELECT 1 FROM chunk_schema.users WHERE id = $1", user_id
            )
            if not user_row:
                return {"status": "error", "message": "User not found"}

            # 校验知识库
            kb_row = await conn.fetchrow(
                "SELECT 1 FROM chunk_schema.knowledge_bases WHERE id = $1 AND user_id = $2",
                knowledge_base_id,
                user_id,
            )
            if not kb_row:
                return {"status": "error", "message": "Knowledge base not found"}

            rows = await conn.fetch(
                "SELECT id, name, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
                knowledge_base_id,
            )
            documents = [
                {"id": r["id"], "name": r["name"], "tags": r["tags"]} for r in rows
            ]
            return {"status": "ok", "documents": documents}
    except Exception as e:
        logger.error(f"get_documents_graph error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if "conn" in locals():
            await conn.close()

async def produce_subject_graph(user_id: str, knowledge_base_id: str):
    return {"status": "ok", "message": "Knowledge base request received"}

async def get_subject_graph(user_id: str, knowledge_base_id: str):
    return {"status": "ok", "message": "Knowledge base request received"}

if __name__ == "__main__":
    asyncio.run(produce_document_graph("123", "456"))