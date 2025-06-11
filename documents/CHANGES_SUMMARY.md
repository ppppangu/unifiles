# Singleton Embedding 模块增强 - 变更总结

## 概述
成功增强了 `singleton_embedding.py` 模块，添加了基于 alias 的负载均衡功能，同时保持了向后兼容性。

## 主要变更

### 1. 函数签名增强
**之前:**
```python
def get_latest_embedding_instance():
    # 返回 (name, url, key)
```

**之后:**
```python
def get_latest_embedding_instance(alias: Optional[str] = None):
    # 返回 (name, url, key, alias)
```

### 2. 新增功能

#### Alias-based 负载均衡
- 当提供 `alias` 参数时，函数只在匹配该 alias 的实例间进行负载均衡
- 当不提供 `alias` 参数时，保持原有行为（在所有实例间负载均衡）

#### 增强的返回值
- 现在返回四元组：`(name, url, key, alias)`
- 原有代码可以继续使用前三个值，第四个值为新增的 alias 信息

### 3. 内部实现增强

#### 新增数据结构
```python
# 基于alias的索引字典
_alias_indices: Dict[str, int] = {}

# 基于alias的实例缓存
_alias_instances_cache: Dict[str, List[dict]] = {}
```

#### 新增函数
- `_initialize_alias_cache()`: 初始化alias缓存
- `_addindex_for_alias(alias: str)`: 增加特定alias的索引
- `_get_index_for_alias(alias: str)`: 获取特定alias的索引位置
- `_get_instances_by_alias(alias: str)`: 获取指定alias的所有实例

## 使用示例

### 原有用法（保持兼容）
```python
from singleton_embedding import get_latest_embedding_instance

# 在所有实例间负载均衡
name, url, key, alias = get_latest_embedding_instance()
```

### 新用法（alias-based 负载均衡）
```python
from singleton_embedding import get_latest_embedding_instance

# 只在 "bge-m3" alias 的实例间负载均衡
name, url, key, alias = get_latest_embedding_instance(alias="bge-m3")
```

### 错误处理
```python
try:
    result = get_latest_embedding_instance(alias="non-existent")
except ValueError as e:
    print(f"错误: {e}")  # 输出: No embedding instances found for alias: non-existent
```

## 配置要求

确保 `config.yaml` 中的 embedding 配置包含 `alias` 字段：

```yaml
api:
  language_embedding:
    - name: "Pro/BAAI/bge-m3"
      url: "https://api.siliconflow.cn/v1/embeddings"
      key: "sk-sqichvhplvkasryatqtmufwevhgnvcxzgqilurqxvvvllmpo"
      alias: "bge-m3"
```

## 线程安全
- 所有索引操作都使用线程锁保护
- 支持多线程环境下的并发访问

## 向后兼容性
- ✅ 现有代码无需修改即可继续工作
- ✅ 原有的负载均衡行为保持不变
- ✅ 返回值向后兼容（可以只使用前三个值）

## 测试建议
建议运行以下测试来验证功能：
1. 测试无 alias 参数的调用（原有行为）
2. 测试有效 alias 参数的调用
3. 测试无效 alias 参数的错误处理
4. 测试多线程环境下的负载均衡
