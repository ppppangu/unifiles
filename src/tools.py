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

# ======================================
# ===========  MIME 类型相关 ============
# ======================================

def detect_content_type(file_name: str, default: str = "application/octet-stream") -> str:
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

# --------------- MinIO URL 内外网自动转换 ----------------

# noinspection PyUnresolvedReferences
def convert_to_internal_minio_url(url: str) -> str:
    """如果 *url* 以 `config.server_components.minio.public_url_prefix` 开头，则替换为
    `http://{host}:{port}` 内网直连地址以供服务器自身访问。

    该方法仅做 *字符串级别* 的替换，不会验证 URL 是否有效。

    Args:
        url: 原始公网 URL

    Returns:
        str: 若匹配到公网前缀则返回内网直连 URL，否则返回原 URL。
    """

    cfg = read_config()  # 读取全局配置
    minio_cfg = cfg.get("server_components", {}).get("minio", {})
    public_prefix: str = str(minio_cfg.get("public_url_prefix", ""))

    # 未配置 public_url_prefix 或者不匹配，直接返回
    if not public_prefix or not url.startswith(public_prefix):
        return url

    host = minio_cfg.get("host")
    port = minio_cfg.get("port")
    if not host or not port:
        # 配置不完整，返回原 URL
        return url

    # 去掉公共前缀后的 path，确保不多余斜杠
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path  # 保留 query/fragment 的场景较少，这里忽略

    internal_url = f"http://{host}:{port}{path}"
    return internal_url




