"""本模块用于持续集成未更新表单结构的pg数据库"""
import asyncpg
import asyncio
from loguru import logger

# 导入配置
from src.tools import (
    read_pg_config,
)


pg_config = read_pg_config()

async def fixpg_public_url_250613():
    # """20250613用于检查并完善chunk_schema.documents表的public_url字段，增加对第一版向量数据库的兼容"""
    # # 连接到数据库
    # logger.info("开始建立数据库连接")
    # conn = await asyncpg.connect(
    #     host=pg_config.get("host"),
    #     port=int(pg_config.get("port")),
    #     user=pg_config.get("user"),
    #     password=pg_config.get("password"),
    #     database=pg_config.get("database")
    # )
    # logger.info("数据库连接建立成功")
    # # 检查chunk_schema.documents表是否有markdown_public_url字段，若存在则跳过，若不存在则添加。
    # try:
    #     async with conn.transaction():
    #         raw_file_public_url_column_check = """
    #         SELECT column_name 
    #         FROM information_schema.columns 
    #         WHERE table_schema = $1 AND table_name = $2 AND column_name = $3
    #         """
    #         raw_file_public_url_column_exists = await conn.fetchrow(raw_file_public_url_column_check, "chunk_schema", "documents", "raw_file_public_url") is not None
    #         if not raw_file_public_url_column_exists:
    #             logger.info("chunk_schema.documents表没有raw_file_public_url字段，添加")
    #             # 添加raw_file_public_url TEXT和markdown_public_url TEXT字段
    #             add_query = "ALTER TABLE chunk_schema.documents ADD COLUMN raw_file_public_url TEXT, ADD COLUMN markdown_public_url TEXT"
    #             await conn.execute(add_query)
    #             logger.info("chunk_schema.documents表已添加raw_file_public_url和markdown_public_url字段")
    #         else:
    #             logger.info("chunk_schema.documents表已有public_url字段，跳过")
    # except Exception as e:
    #     logger.error(f"检查chunk_schema.documents表的raw_file_public_url字段时发生错误: {e}")
    # finally:
    #     await conn.close()

    pass
if __name__ == "__main__":
    asyncio.run(fixpg_public_url_250613())