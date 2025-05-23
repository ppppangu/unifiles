import asyncio
import uuid
from typing import List

import psycopg2
from src.read_yaml import read_config

# ------------------------------------
# 连接信息
# ------------------------------------
config = read_config()
DB_HOST = config["vectorbase"]["postgres"]["host"]
DB_PORT = int(config["vectorbase"]["postgres"]["port"])
DB_NAME = config["vectorbase"]["postgres"]["database"]
DB_USER = config["vectorbase"]["postgres"]["user"]
DB_PASSWORD = config["vectorbase"]["postgres"]["password"]


# ------------------------------------
# 主逻辑函数
# ------------------------------------
async def insert_chunks(
    chunks: List[str],
    embeddings: List[List[float]],
    knowledge_base_id: str,
    document_id: str,
    user_id: str = "default_user",
):
    """按照新表结构写入数据 (同步 I/O 封装到线程池)"""

    assert len(chunks) == len(embeddings), "chunks / embeddings 对齐失败"

    await asyncio.to_thread(
        _insert_sync,
        chunks,
        embeddings,
        knowledge_base_id,
        document_id,
        user_id,
    )


def _insert_sync(
    chunks: List[str],
    embeddings: List[List[float]],
    knowledge_base_id: str,
    document_id: str,
    user_id: str,
):
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cur = conn.cursor()

        # 创建 schema & 表 (若不存在)
        cur.execute("CREATE SCHEMA IF NOT EXISTS chunk_schema;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_schema.users(
                id TEXT PRIMARY KEY,
                knowledge_ids TEXT[] DEFAULT '{}'
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_schema.knowledge_bases (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
                name TEXT,
                description TEXT,
                document_ids TEXT[] DEFAULT '{}'::TEXT[]
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_schema.documents (
                id TEXT PRIMARY KEY,
                knowledge_base_id TEXT NOT NULL REFERENCES chunk_schema.knowledge_bases(id) ON DELETE CASCADE,
                name TEXT,
                text TEXT,
                component_ids TEXT[] DEFAULT '{}',
                hierarchy_path ltree DEFAULT 'root'::ltree
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_schema.chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
                text TEXT,
                embedding vector,
                doc_position INTEGER
            );
            """
        )

        # upsert user & kb & doc
        cur.execute(
            "INSERT INTO chunk_schema.users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING;",
            (user_id,),
        )
        cur.execute(
            "INSERT INTO chunk_schema.knowledge_bases (id, user_id) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING;",
            (knowledge_base_id, user_id),
        )
        cur.execute(
            "INSERT INTO chunk_schema.documents (id, knowledge_base_id, name) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;",
            (document_id, knowledge_base_id, document_id),
        )

        # 删除旧 chunks
        cur.execute(
            "DELETE FROM chunk_schema.chunks WHERE document_id = %s;", (document_id,)
        )

        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            emb_str = f"[{','.join(map(str, emb))}]"
            cur.execute(
                """
                INSERT INTO chunk_schema.chunks (id, document_id, text, embedding, doc_position)
                VALUES (%s, %s, %s, %s::vector, %s);
                """,
                (chunk_id, document_id, chunk_text, emb_str, idx),
            )
        conn.commit()
    finally:
        if conn:
            conn.close()