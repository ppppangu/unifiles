"""
本模块使用单例模式用于将配置文件中的tavilyAPI调用接口自动进行负载均衡
"""
import threading
import yaml
from pathlib import Path

# 读取全局embedding的配置文件
with open(Path(__file__).parent.parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)
tavily_api_list = config["search"]["web_search"]["tavily"]

# 定义全局线程锁
_lock = threading.Lock()

_tavily_api_instances = tavily_api_list
_tavily_api_instances_num = len(_tavily_api_instances)

# 定义全局共享索引
_shared_index = 0

# 增加共享索引
def _addindex():
    global _shared_index
    with _lock:
        _shared_index += 1
        if _shared_index > _tavily_api_instances_num-1:
            _shared_index = 0

# 获取共享索引位置
def _get_index():
    return _shared_index

# 解析tavily函数
def _parse_instance_config(config: str):
    """
    解析tavily的实例配置
    """
    # 配置项已经是字符串类型的API密钥，直接返回
    return config

# 获取最新索引位置的tavily实例
def get_latest_tavily_api_instance() -> str:
    latest_index = _get_index()
    _addindex()
    return str(_parse_instance_config(_tavily_api_instances[latest_index]))
