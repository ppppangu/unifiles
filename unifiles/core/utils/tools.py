from pathlib import Path

import asyncpg
import yaml
from asyncpg import Connection
from loguru import logger
from minio import Minio

# ======================================
# ===========  配置文件相关 =============
# ======================================


# 读取配置文件
def read_config() -> dict:
    """读取配置文件"""
    config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


# 读取向量数据库配置
def read_pg_config() -> dict:
    config = read_config()
    pg_config = config["server_components"]["pg_vector"].copy()

    # 解析address字段为host和port
    if "address" in pg_config:
        address = pg_config["address"]
        if ":" in address:
            host, port = address.rsplit(":", 1)
            pg_config["host"] = host
            pg_config["port"] = int(port)
        else:
            pg_config["host"] = address
            pg_config["port"] = 5432  # 默认PostgreSQL端口

    return pg_config


# 读取minio配置
def read_minio_config() -> dict:
    config = read_config()
    minio_config = config["server_components"]["minio"].copy()

    # 解析address字段为host和port（为了向后兼容）
    if "address" in minio_config:
        address = minio_config["address"]
        if ":" in address:
            host, port = address.rsplit(":", 1)
            minio_config["host"] = host
            minio_config["port"] = int(port)
        else:
            minio_config["host"] = address
            minio_config["port"] = 9000  # 默认MinIO端口

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


# ======================================
# ===========  MIME 类型相关 ============
# ======================================


def detect_content_type(
    file_name: str, default: str = "application/octet-stream"
) -> str:
    """根据文件扩展名智能检测 Content-Type。

    参数:
        file_name: 文件名或路径, 用于提取扩展名
        default: 无法识别时返回的默认 Content-Type

    返回:
        合适的 MIME 类型字符串, 失败时返回 default
    """
    import mimetypes

    # 先使用标准库猜测
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type:
        return mime_type

    # 扩展自定义映射
    from pathlib import Path

    ext = Path(file_name).suffix.lower()

    custom_mapping = {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".yml": "application/x-yaml",
        ".yaml": "application/x-yaml",
    }

    return custom_mapping.get(ext, default)


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
        (
            minio_config["address"]
            if "address" in minio_config
            else f"{minio_config['host']}:{minio_config['port']}"
        ),
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False,
    )
    try:
        # 检查桶内是否存在以用户id命名的目录
        objects = minio_client.list_objects(
            minio_config["bucket_name"], prefix=f"{user_id}/", recursive=False
        )
        return any(True for _ in objects)
    except Exception as e:
        logger.error(f"Error checking user_id in MinIO: {e}")
        return False

