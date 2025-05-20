# 上传文件的接口中没有用户id，所以需要查一下
import asyncpg
from asyncpg import Connection

async def get_user_id_by_knowledge_base_id(knowledge_base_id: str, connection: Connection):
    query = "SELECT user_id FROM chunk_schema.knowledge_bases WHERE id = $1"
    user_id = await connection.fetchval(query, knowledge_base_id)
    if not user_id:
        user_id = ""
    return user_id

# 以下为测试代码
async def main():
    # 从环境变量加载数据库配置
    from dotenv import load_dotenv
    import os

    load_dotenv()

    # 创建数据库连接
    conn = await asyncpg.connect(
        host="100.69.179.6",
        port=5437,
        user="postgres",
        password="postgres",
        database="postgres"
    )

    try:
        # 执行查询
        example_knowledge_base_id = "kb-bf9a491b-9123-432b-8d71-9e4934425b86"
        user_id = await get_user_id_by_knowledge_base_id(example_knowledge_base_id, conn)
        print(user_id)
    finally:
        # 关闭连接
        await conn.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

