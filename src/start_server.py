from loguru import logger
from pathlib import Path
from datetime import datetime
import asyncpg
from tools import read_config

# 读取配置
config = read_config()
server_components = config["server_components"]
pg_vector_config = server_components["pg_vector"] if config["server_components"]["pg_vector"]["active"] else None
minio_config = server_components["minio"] if config["server_components"]["minio"]["active"] else None
mineru_config = server_components["mineru"] if config["server_components"]["mineru"]["active"] else None
convert_format_server_config = server_components["convert_format_server"] if config["server_components"]["convert_format_server"]["active"] else None

async def start_up_check():
    # 设置日志
    log_path = str(Path(__file__).parent.parent / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log")
    logger.add(log_path, enqueue=True, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",level="INFO")
    logger.info("===================start up====================")
    logger.info("file server begin to start up! server components:")
    logger.info(f"pg_vector: {pg_vector_config['host']}:{pg_vector_config['port']}")
    logger.info(f"minio: {minio_config['host']}:{minio_config['port']}")
    logger.info(f"mineru: {mineru_config['url']}")
    logger.info(f"convert_format_server: {convert_format_server_config['url']}")
    
    # 检查向量数据库连接
    if pg_vector_config is not None:
        try:
            test_pg_connection = await asyncpg.connect(
                host=pg_vector_config["host"],
                port=int(pg_vector_config["port"]),
                user=pg_vector_config["user"],
                password=pg_vector_config["password"],
                database=pg_vector_config["database"]
            )
            await test_pg_connection.close()
            logger.info(f"vector database connection test passed! | Vector database(postgres) is working on {pg_vector_config['host']}:{pg_vector_config['port']}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL, config_url: postgres://{pg_vector_config['user']}:{pg_vector_config['password']}@{pg_vector_config['host']}:{pg_vector_config['port']}/{pg_vector_config['database']}, error: {e}")
        finally:
            try:
                await test_pg_connection.close()
            except Exception as e:
                pass

    # 检查S3连接
    try:
        # 使用自定义配置创建S3客户端
        test_s3_connection = await async_get_s3_connection(minio_config["endpoint_url"], minio_config["access_key"], minio_config["secret_access_key"], minio_config["region"])
        await test_s3_connection.list_buckets()
        logger.info(f"s3 connection test passed!              | S3 is working on {minio_config['endpoint_url']}")
    except Exception as e:
        logger.error(f"Failed to connect to S3, config_url: s3://{minio_config['access_key']}:{minio_config['secret_access_key']}@{minio_config['endpoint_url']}, error: {e}")
    finally:
        try:
            await test_s3_connection.close()
        except Exception as e:
            pass

    # 检查MinerU的服务端连接
    for mineru_url in FILE_SERVER_MINERU_URL_LIST:
        try:
            test_s3_connection = await async_get_s3_connection(FILE_SERVER_S3_ENDPOINT_URL, FILE_SERVER_S3_ACCESS_KEY, FILE_SERVER_S3_SECRET_ACCESS_KEY, FILE_SERVER_S3_REGION)
            await test_s3_connection.list_buckets()
            mineru_client = MinerUClient(
                mineru_url=mineru_url,
                file_content=None,
                s3_connection=test_s3_connection
            )
            await mineru_client.health()
            logger.info(f"mineru connection test passed!          | MinerU is working on {mineru_url}")
        except Exception as e:
            logger.error(f"Failed to initialize MinerUClient, mineru_url: {mineru_url}, error: {e}")
        finally:
            try:
                await test_s3_connection.close()
            except Exception as e:
                pass
    logger.info("==================start up=======================")

