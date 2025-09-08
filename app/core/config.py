from pathlib import Path
from typing import Dict, Any
import yaml
from pydantic import BaseModel
from loguru import logger


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8087
    

class MinioConfig(BaseModel):
    """MinIO配置"""
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    public_url_prefix: str = ""


class PgVectorConfig(BaseModel):
    """PgVector数据库配置"""
    host: str
    port: int
    database: str
    user: str
    password: str


class Config(BaseModel):
    """应用配置"""
    server: ServerConfig = ServerConfig()
    minio: MinioConfig
    pg_vector: PgVectorConfig


def load_config() -> Config:
    """加载配置文件"""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
    
    # 转换配置结构
    config_data = {
        "server": raw_config.get("server", {}),
        "minio": raw_config["server_components"]["minio"],
        "pg_vector": raw_config["server_components"]["pg_vector"]
    }
    
    logger.info("配置文件加载成功")
    return Config(**config_data)


def create_directories() -> None:
    """创建必要的目录结构"""
    base_path = Path(__file__).parent.parent.parent
    
    directories = [
        base_path / "logs",
        base_path / "tmp"
    ]
    
    for directory in directories:
        directory.mkdir(mode=0o777, exist_ok=True)
        logger.debug(f"创建目录: {directory}")


# 全局配置实例
config = load_config()