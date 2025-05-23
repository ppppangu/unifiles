"""
本模块使用单例模式用于将配置文件中的多模态嵌入模型的接口自动进行负载均衡
"""
import threading
import yaml
from pathlib import Path

# 读取全局embedding的配置文件
with open(Path(__file__).parent.parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)
readed_multimodal_embedding_list = config["api"]["multimodal_embedding"]

# 定义全局线程锁
_lock = threading.Lock()

_multimodal_embedding_instances = readed_multimodal_embedding_list
_multimodal_embedding_instances_num = len(_multimodal_embedding_instances)

# 定义全局共享索引
_shared_index = 0

# 增加共享索引
def _addindex():
    global _shared_index
    with _lock:
        _shared_index += 1
        if _shared_index > _multimodal_embedding_instances_num-1:
            _shared_index = 0

# 获取共享索引位置
def _get_index():
    return _shared_index

# 解析多模态模型的函数
def _parse_instance_config(config: str):
    """
    解析多模态嵌入模型的实例配置
    """
    name = config["name"]
    url = config["url"]
    key = config["key"]
    return name, url, key

# 获取最新索引位置的多模态模型实例
def get_latest_multimodal_embedding_instance():
    latest_index = _get_index()
    _addindex()
    return _parse_instance_config(_multimodal_embedding_instances[latest_index])


