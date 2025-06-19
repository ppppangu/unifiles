"""
本模块使用单例模式用于将配置文件中的embedding模型、多模态LLM和语言LLM自动进行负载均衡
支持基于type和alias的负载均衡，可以在特定类型或alias的实例间进行负载均衡
支持的类型: language_embedding, multimodal_llm, language_llm
"""
import threading
import yaml
from pathlib import Path
from typing import Optional, List, Dict

# 读取全局配置文件
with open(Path(__file__).parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)
readed_language_embeddings_list = config["api"]["language_embedding"]
readed_multimodal_llm_list = config["api"]["multimodal_llm"]
readed_language_llm_list = config["api"]["language_llm"]

# 定义全局线程锁
_lock = threading.Lock()

# 合并所有实例
_all_instances = readed_language_embeddings_list + readed_multimodal_llm_list + readed_language_llm_list
_all_instances_num = len(_all_instances)

# 按类型分组的实例
_type_instances: Dict[str, List[dict]] = {
    "language_embedding": readed_language_embeddings_list,
    "multimodal_llm": readed_multimodal_llm_list,
    "language_llm": readed_language_llm_list
}

# 定义全局共享索引（用于所有实例的负载均衡）
_shared_index = 0

# 定义基于type的索引字典
_type_indices: Dict[str, int] = {}

# 定义基于alias的索引字典（用于特定alias的负载均衡）
_alias_indices: Dict[str, int] = {}

# 定义基于alias的实例缓存
_alias_instances_cache: Dict[str, List[dict]] = {}

# 初始化alias实例缓存
def _initialize_alias_cache():
    """初始化基于alias的实例缓存"""
    global _alias_instances_cache, _alias_indices
    with _lock:
        _alias_instances_cache.clear()
        _alias_indices.clear()

        for instance in _all_instances:
            alias = instance.get("alias")
            if alias:
                if alias not in _alias_instances_cache:
                    _alias_instances_cache[alias] = []
                    _alias_indices[alias] = 0
                _alias_instances_cache[alias].append(instance)

# 在模块加载时初始化缓存
_initialize_alias_cache()

# 增加共享索引（用于所有实例的负载均衡）
def _addindex():
    global _shared_index
    with _lock:
        _shared_index += 1
        if _shared_index > _all_instances_num-1:
            _shared_index = 0

# 增加特定alias的索引
def _addindex_for_alias(alias: str):
    global _alias_indices
    with _lock:
        if alias in _alias_indices and alias in _alias_instances_cache:
            _alias_indices[alias] += 1
            alias_instances_num = len(_alias_instances_cache[alias])
            if _alias_indices[alias] > alias_instances_num - 1:
                _alias_indices[alias] = 0

# 增加特定type的索引
def _addindex_for_type(instance_type: str):
    global _type_indices
    with _lock:
        if instance_type in _type_instances:
            if instance_type not in _type_indices:
                _type_indices[instance_type] = 0
            _type_indices[instance_type] += 1
            type_instances_num = len(_type_instances[instance_type])
            if _type_indices[instance_type] > type_instances_num - 1:
                _type_indices[instance_type] = 0

# 获取共享索引位置
def _get_index():
    return _shared_index

# 获取特定alias的索引位置
def _get_index_for_alias(alias: str) -> int:
    if alias in _alias_indices:
        return _alias_indices[alias]
    return 0

# 获取特定type的索引位置
def _get_index_for_type(instance_type: str) -> int:
    if instance_type in _type_indices:
        return _type_indices[instance_type]
    return 0

# 解析embedding的函数
def _parse_instance_config(config: dict):
    """
    解析embedding的实例配置
    """
    name = config["name"]
    url = config["url"]
    key = config["key"]
    alias = config.get("alias", "")
    return name, url, key, alias

# 获取特定alias的实例列表
def _get_instances_by_alias(alias: str) -> List[dict]:
    """获取指定alias的所有实例"""
    if alias in _alias_instances_cache:
        return _alias_instances_cache[alias]
    return []

# 获取特定type的实例列表
def _get_instances_by_type(instance_type: str) -> List[dict]:
    """获取指定type的所有实例"""
    if instance_type in _type_instances:
        return _type_instances[instance_type]
    return []

# 获取最新索引位置的embedding实例
def get_latest_embedding_instance(alias: Optional[str] = None, instance_type: Optional[str] = None):
    """
    获取最新索引位置的embedding实例

    Args:
        alias: 可选的alias参数，如果提供则只在该alias的实例间进行负载均衡
        instance_type: 可选的type参数，如果提供则只在该type的实例间进行负载均衡
                      支持的类型: 'language_embedding', 'multimodal_llm', 'language_llm'

    注意: alias和instance_type参数是互斥的，不能同时使用

    Returns:
        tuple: (name, url, key, alias) 的元组
    """
    # 检查参数互斥性
    if alias is not None and instance_type is not None:
        raise ValueError("alias and instance_type parameters are mutually exclusive. Please specify only one.")

    if alias:
        # 基于alias的负载均衡
        alias_instances = _get_instances_by_alias(alias)
        if not alias_instances:
            raise ValueError(f"No instances found for alias: {alias}")

        latest_index = _get_index_for_alias(alias)
        _addindex_for_alias(alias)
        return _parse_instance_config(alias_instances[latest_index])
    elif instance_type:
        # 基于type的负载均衡
        type_instances = _get_instances_by_type(instance_type)
        if not type_instances:
            raise ValueError(f"No instances found for type: {instance_type}. Supported types: {list(_type_instances.keys())}")

        latest_index = _get_index_for_type(instance_type)
        _addindex_for_type(instance_type)
        return _parse_instance_config(type_instances[latest_index])
    else:
        # 全局负载均衡（原有行为）
        latest_index = _get_index()
        _addindex()
        return _parse_instance_config(_all_instances[latest_index])


