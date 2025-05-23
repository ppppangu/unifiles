"""
本模块使用单例模式用于将配置文件中的e2b_sandbox的API自动进行负载均衡
"""
import threading
import yaml
from pathlib import Path

# 读取全局e2b_sandbox的配置文件
with open(Path(__file__).parent.parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)
readed_e2b_sandbox_list = config["mcp"]["e2b_sandbox"]

# 定义全局线程锁
_lock = threading.Lock()

_e2b_sandbox_instances = readed_e2b_sandbox_list
_e2b_sandbox_instances_num = len(_e2b_sandbox_instances)

# 定义全局共享索引
_shared_index = 0

# 增加共享索引
def _addindex():
    global _shared_index
    with _lock:
        _shared_index += 1
        if _shared_index > _e2b_sandbox_instances_num-1:
            _shared_index = 0

# 获取共享索引位置
def _get_index():
    return _shared_index

# 解析e2b_sandbox的函数
def _parse_instance_config(config: str):
    """
    解析e2b_sandbox的实例配置
    """
    name = config["name"]
    url = config["url"]
    key = config["key"]
    return name, url, key

# 获取最新索引位置的e2b_sandbox实例
def get_latest_e2b_sandbox_instance():
    latest_index = _get_index()
    _addindex()
    return _parse_instance_config(_e2b_sandbox_instances[latest_index])


