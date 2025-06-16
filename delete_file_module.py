from loguru import logger
import asyncpg
import yaml
from pathlib import Path

# 读取配置文件
def read_config() -> dict:
    """读取配置文件"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

async def delete_file_from_vcdb(user_id: str, file_id: str, knowledge_base_id: str):
    """
    从向量数据库中删除文件及其所有相关数据

    基于数据库建表逻辑和触发器设计，该函数的工作原理：

    1. 数据库层次结构理解：
       Users → Knowledge Bases → Documents → Components → Chunks/Photos

    2. 触发器自动处理机制：
       - 删除documents表记录时，ON DELETE CASCADE会自动删除：
         * 所有相关的components记录 (document_id外键)
         * 所有相关的chunks记录 (document_id外键)
         * 所有相关的photos记录 (document_id外键)
       - 触发器update_knowledge_base_document_ids()会自动：
         * 从knowledge_bases.document_ids数组中移除被删除的document_id

    3. 权限验证逻辑：
       - 验证knowledge_base_id确实属于user_id (防止跨用户删除)
       - 验证document_id确实属于knowledge_base_id (防止跨知识库删除)

    4. 删除策略：
       - 只需删除documents表中的目标记录
       - 数据库触发器会自动处理所有级联删除和数组更新
       - 这确保了数据一致性，避免了孤立记录

    Args:
        user_id: 用户ID
        file_id: 文件ID（即document_id）
        knowledge_base_id: 知识库ID

    Returns:
        bool: 删除成功返回True，失败返回False

    Raises:
        ValueError: 参数验证失败或权限验证失败
        Exception: 数据库操作失败
    """
    # 参数验证
    if not user_id or not user_id.strip():
        raise ValueError("user_id cannot be empty")
    if not file_id or not file_id.strip():
        raise ValueError("file_id cannot be empty")
    if not knowledge_base_id or not knowledge_base_id.strip():
        raise ValueError("knowledge_base_id cannot be empty")

    # 获取数据库配置
    config = read_config()
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
            # 开始事务 - 确保所有操作的原子性
            async with conn.transaction():
                # 第一步：验证knowledge_base_id是否属于user_id
                # 这确保用户只能删除自己拥有的知识库中的文档
                kb_check_query = """
                    SELECT id FROM chunk_schema.knowledge_bases
                    WHERE id = $1 AND user_id = $2
                """
                kb_result = await conn.fetchrow(kb_check_query, knowledge_base_id, user_id)

                if not kb_result:
                    raise ValueError(f"Knowledge base {knowledge_base_id} does not belong to user {user_id} or does not exist")

                # 第二步：验证document_id是否属于knowledge_base_id
                # 这确保文档确实存在于指定的知识库中
                doc_check_query = """
                    SELECT id FROM chunk_schema.documents
                    WHERE id = $1 AND knowledge_base_id = $2
                """
                doc_result = await conn.fetchrow(doc_check_query, file_id, knowledge_base_id)

                if not doc_result:
                    raise ValueError(f"Document {file_id} does not belong to knowledge base {knowledge_base_id} or does not exist")

                # 第三步：执行删除操作
                # 根据数据库建表逻辑，删除documents表记录会触发以下自动操作：
                #
                # 1. ON DELETE CASCADE 级联删除：
                #    - chunk_schema.components 表中所有 document_id = file_id 的记录
                #    - chunk_schema.chunks 表中所有 document_id = file_id 的记录
                #    - chunk_schema.photos 表中所有 document_id = file_id 的记录
                #
                # 2. 触发器 document_after_trigger 会调用 update_knowledge_base_document_ids()：
                #    - 从 knowledge_bases.document_ids 数组中移除被删除的 document_id
                #    - 保持知识库的文档索引数组与实际文档的一致性
                #
                # 这种设计的优势：
                # - 确保数据一致性，避免孤立记录
                # - 自动维护索引数组，无需手动更新
                # - 减少代码复杂度，降低出错概率
                delete_query = """
                    DELETE FROM chunk_schema.documents
                    WHERE id = $1 AND knowledge_base_id = $2
                """
                result = await conn.execute(delete_query, file_id, knowledge_base_id)

                # 检查删除结果
                # result 格式为 "DELETE n"，其中 n 是被删除的行数
                if result == "DELETE 0":
                    logger.warning(f"No document found to delete - document_id: {file_id}, knowledge_base_id: {knowledge_base_id}")
                    return False

                # 记录成功删除的详细信息
                logger.info(f"Successfully deleted document from vector database - "
                          f"document_id: {file_id}, knowledge_base_id: {knowledge_base_id}, "
                          f"user_id: {user_id}")

                # 记录触发器自动处理的操作
                logger.info(f"Database triggers automatically handled: "
                          f"1) Cascade deleted all components, chunks, and photos for document {file_id}; "
                          f"2) Updated knowledge_base {knowledge_base_id} document_ids array")

                return True

        finally:
            await conn.close()

    except ValueError as e:
        logger.error(f"Validation error when deleting document: {e}")
        raise
    except asyncpg.exceptions.ForeignKeyViolationError as e:
        logger.error(f"Foreign key constraint violation when deleting document: {e}")
        raise ValueError(f"Cannot delete document due to foreign key constraints: {str(e)}")
    except asyncpg.exceptions.ConnectionDoesNotExistError as e:
        logger.error(f"Database connection error: {e}")
        raise Exception(f"Database connection failed: {str(e)}")
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error when deleting document: {e}")
        raise Exception(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to delete document from vector database: {e}")
        raise Exception(f"Database operation failed: {str(e)}")

async def delete_file_from_minio(user_id: str, file_id: str, knowledge_base_id: str):
    """
    从MinIO对象存储中删除文件及其相关文件

    文件存储路径结构：
    1. 主要路径：{user_id}/knowledgebase/{knowledge_base_id}/{file_id}/
    2. 默认路径：{user_id}/default_file_space/{file_id}/

    删除策略：
    1. 首先尝试删除主要路径下的所有文件
    2. 如果主要路径不存在或为空，尝试删除默认路径下的文件
    3. 删除整个文件目录（包括所有相关文件：原文件、.md文件、.json文件等）

    Args:
        user_id: 用户ID
        file_id: 文件ID（即document_id，也是MinIO中的目录名）
        knowledge_base_id: 知识库ID

    Returns:
        bool: 删除成功返回True，失败返回False

    Raises:
        ValueError: 参数验证失败
        Exception: MinIO操作失败
    """
    # 参数验证
    if not user_id or not user_id.strip():
        raise ValueError("user_id cannot be empty")
    if not file_id or not file_id.strip():
        raise ValueError("file_id cannot be empty")
    if not knowledge_base_id or not knowledge_base_id.strip():
        raise ValueError("knowledge_base_id cannot be empty")

    # 获取MinIO配置
    config = read_config()
    minio_config = config["server_components"]["minio"]

    try:
        # 导入MinIO客户端
        from minio import Minio

        # 创建MinIO客户端
        minio_client = Minio(
            f"{minio_config['host']}:{minio_config['port']}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False  # 根据配置调整
        )

        bucket_name = minio_config["bucket_name"]

        # 检查桶是否存在
        if not minio_client.bucket_exists(bucket_name):
            logger.warning(f"Bucket {bucket_name} does not exist")
            return False

        # 定义可能的文件路径
        primary_path = f"{user_id}/knowledgebase/{knowledge_base_id}/{file_id}/"
        default_path = f"{user_id}/default_file_space/{file_id}/"

        deleted_files = []

        # 尝试删除主要路径下的文件
        try:
            objects = minio_client.list_objects(bucket_name, prefix=primary_path, recursive=True)
            primary_files = list(objects)

            if primary_files:
                logger.info(f"Found {len(primary_files)} files in primary path: {primary_path}")

                for obj in primary_files:
                    try:
                        minio_client.remove_object(bucket_name, obj.object_name)
                        deleted_files.append(obj.object_name)
                        logger.debug(f"Deleted file: {obj.object_name}")
                    except Exception as e:
                        logger.error(f"Failed to delete file {obj.object_name}: {e}")

                logger.info(f"Successfully deleted {len(deleted_files)} files from primary path")
            else:
                logger.info(f"No files found in primary path: {primary_path}")

        except Exception as e:
            logger.error(f"Error listing/deleting files from primary path {primary_path}: {e}")

        # 如果主要路径没有文件，尝试默认路径
        if not deleted_files:
            try:
                objects = minio_client.list_objects(bucket_name, prefix=default_path, recursive=True)
                default_files = list(objects)

                if default_files:
                    logger.info(f"Found {len(default_files)} files in default path: {default_path}")

                    for obj in default_files:
                        try:
                            minio_client.remove_object(bucket_name, obj.object_name)
                            deleted_files.append(obj.object_name)
                            logger.debug(f"Deleted file: {obj.object_name}")
                        except Exception as e:
                            logger.error(f"Failed to delete file {obj.object_name}: {e}")

                    logger.info(f"Successfully deleted {len(deleted_files)} files from default path")
                else:
                    logger.info(f"No files found in default path: {default_path}")

            except Exception as e:
                logger.error(f"Error listing/deleting files from default path {default_path}: {e}")

        # 检查删除结果
        if deleted_files:
            logger.info(f"Successfully deleted file from MinIO - "
                      f"file_id: {file_id}, user_id: {user_id}, "
                      f"knowledge_base_id: {knowledge_base_id}, "
                      f"total_files_deleted: {len(deleted_files)}")

            # 记录删除的文件列表（仅记录前几个，避免日志过长）
            if len(deleted_files) <= 5:
                logger.info(f"Deleted files: {deleted_files}")
            else:
                logger.info(f"Deleted files (first 5): {deleted_files[:5]}... and {len(deleted_files)-5} more")

            return True
        else:
            logger.warning(f"No files found to delete for file_id: {file_id}, "
                         f"user_id: {user_id}, knowledge_base_id: {knowledge_base_id}")
            return False

    except ValueError as e:
        logger.error(f"Validation error when deleting file from MinIO: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to delete file from MinIO: {e}")
        raise Exception(f"MinIO operation failed: {str(e)}")