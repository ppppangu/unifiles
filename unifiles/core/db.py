import asyncpg
from loguru import logger

from server.core.utils.tools import read_pg_config

pg_config = read_pg_config()


async def ensure_user_exists(user_id: str) -> None:
    """确保用户在数据库中存在，如果不存在则创建。"""
    conn = None
    try:
        conn = await asyncpg.connect(**pg_config)
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.users WHERE id = $1)", user_id
        )
        if not exists:
            await conn.execute(
                "INSERT INTO chunk_schema.users (id) VALUES ($1)", user_id
            )
            logger.info(f"Created new user in database: {user_id}")
    except Exception as e:
        logger.error(f"Error ensuring user exists: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def add_file_record(
    file_id: str,
    user_id: str,
    filename: str,
    file_size: int,
    content_type: str,
    object_path: str,
    public_url: str,
) -> None:
    """将文件记录添加到数据库。"""
    conn = None
    try:
        await ensure_user_exists(user_id)
        conn = await asyncpg.connect(**pg_config)
        await conn.execute(
            """
            INSERT INTO chunk_schema.files (
                id, user_id, bytes, filename, mime_type,
                file_path, raw_file_public_url, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            file_id,
            user_id,
            file_size,
            filename,
            content_type,
            object_path,
            public_url,
            "uploaded",
        )
        logger.info(f"File record created in database: {file_id}")
    except Exception as e:
        logger.error(f"Error recording file to database: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def get_file_record(file_id: str):
    """根据文件ID从数据库获取文件记录。"""
    conn = None
    try:
        conn = await asyncpg.connect(**pg_config)
        # user_id is needed for authorization checks in the calling function
        file_record = await conn.fetchrow(
            """
            SELECT id, filename, bytes, mime_type, raw_file_public_url,
                   file_path, created_at, user_id
            FROM chunk_schema.files
            WHERE id = $1
            """,
            file_id,
        )
        return file_record
    except Exception as e:
        logger.error(f"Error getting file record from DB: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def get_user_files(user_id: str, limit: int = 50, offset: int = 0):
    """获取用户的所有文件记录。"""
    conn = None
    try:
        conn = await asyncpg.connect(**pg_config)
        file_records = await conn.fetch(
            """
            SELECT id, filename, bytes, mime_type, raw_file_public_url,
                   file_path, created_at, user_id
            FROM chunk_schema.files
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        return file_records
    except Exception as e:
        logger.error(f"Error getting user files from DB: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def delete_file_record(file_id: str) -> None:
    """根据文件ID从数据库删除文件记录。"""
    conn = None
    try:
        conn = await asyncpg.connect(**pg_config)
        result = await conn.execute("DELETE FROM chunk_schema.files WHERE id = $1", file_id)
        if " 0" in result:
            logger.warning(f"Attempted to delete non-existent file record from DB: {file_id}")
        else:
            logger.info(f"File record deleted from database: {file_id}")
    except Exception as e:
        logger.error(f"Error deleting file record from DB: {e}")
        raise
    finally:
        if conn:
            await conn.close()
