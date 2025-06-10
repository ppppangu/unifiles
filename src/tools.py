import asyncpg
from asyncpg import Connection
import yaml
from pathlib import Path
from minio import Minio
from loguru import logger

# ======================================
# ===========  配置文件相关 =============
# ======================================

# 读取配置文件
def read_config() -> dict:
    """读取配置文件"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

# 读取向量数据库配置
def read_pg_config() -> dict:
    config = read_config()
    pg_config = config["server_components"]["pg_vector"]
    return pg_config

# 读取minio配置
def read_minio_config() -> dict:
    config = read_config()
    minio_config = config["server_components"]["minio"]
    return minio_config

# 创建日志目录
def mk_logs_path() -> None:
    log_path = Path(__file__).parent / "logs"
    log_path.mkdir(mode=777, exist_ok=True)

# 创建临时目录
def mk_temp_path() -> None:
    temp_path = Path(__file__).parent / "tmp"
    temp_path.mkdir(mode=777, exist_ok=True)

# 创建必要目录
def mk_need_path() -> None:
    mk_logs_path()
    mk_temp_path()

# 验证用户id在数据库和minio中是否存在
async def validate_user_id(user_id: str) -> bool:
    pg_config = read_pg_config()
    async with asyncpg.create_pool(**pg_config) as pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                query = "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)"
                result = await conn.fetch(query, user_id)
                return result[0]["exists"]

# 验证用户id在minio中是否存在, 看桶内是否存在以用户id命名的目录
async def validate_user_id_in_minio(user_id: str) -> bool:
    minio_config = read_minio_config()
    minio_client = Minio(
        f"{minio_config['host']}:{minio_config['port']}",
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False
    )
    try:
        # 检查桶内是否存在以用户id命名的目录
        objects = minio_client.list_objects(minio_config["bucket_name"], prefix=f"{user_id}/", recursive=False)
        return any(True for _ in objects)
    except Exception as e:
        logger.error(f"Error checking user_id in MinIO: {e}")
        return False




