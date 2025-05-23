"""
本模块使用单例模式用于将配置文件中的s3的API自动进行负载均衡
"""
import threading
import yaml
from pathlib import Path

# 读取全局s3的配置文件
with open(Path(__file__).parent.parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)
readed_s3_list = config["s3"]