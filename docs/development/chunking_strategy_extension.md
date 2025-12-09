# 如何扩展分块策略 (Chunking Strategies)

本项目采用了灵活的 **接口 + 注册表 (Interface + Registry)** 模式来实现文档分块。这允许您在不修改核心 `ChunkingService` 逻辑的情况下添加新的分块算法。

## 架构概览

*   **`BaseChunker`**: 定义接口的抽象基类。
*   **`@register_chunker`**: 一个装饰器，用于将您的类注册到全局注册表中。
*   **`ChunkingService`**: 自动发现并使用已注册的策略。

## 分步指南

### 1. 定义您的策略名称
首先，为您的策略确定一个唯一的字符串标识符（例如 `"my_custom_strategy"`）。
（可选）建议将其添加到 `unifiles/core/services/chunking_service.py` 中的 `ChunkingStrategy` 枚举中以获得更好的类型安全，但这并不是强制要求的。

### 2. 实现分块器类
创建一个继承自 `BaseChunker` 的新类。您必须实现以下方法：
*   `__init__`: 接收 `**kwargs` 以处理灵活的配置参数。
*   `chunk`: 接收文本并返回分块字典列表。

**代码示例：**

```python
from typing import List, Dict, Any
from unifiles.core.services.chunking_service import BaseChunker, register_chunker

@register_chunker("regex_custom")
class RegexCustomChunker(BaseChunker):
    def __init__(self, pattern: str = r"\n\n", **kwargs):
        self.pattern = pattern
        # 必须接收 **kwargs 以防止 TypeError
        # 这里可以处理其他自定义参数
    
    def chunk(self, text: str) -> List[Dict[str, Any]]:
        import re
        chunks = []
        parts = re.split(self.pattern, text)
        
        for idx, part in enumerate(parts):
            if not part.strip():
                continue
                
            chunks.append({
                "content": part.strip(),
                "index": idx,
                "type": "text",
                "metadata": {
                    "strategy": "regex_custom",
                    "char_count": len(part)
                }
            })
        return chunks
```

### 3. 使用方法
一旦注册（通过导入模块），虽然无需修改 Service 代码，您就可以立即通过 Service 使用它：

```python
from unifiles.core.services.chunking_service import get_chunking_service

service = get_chunking_service()
chunks = service.chunk_markdown(
    text, 
    strategy="regex_custom", 
    pattern=r"\n---\n"  # 直接传递自定义参数
)
```

## 最佳实践

1.  **在 `__init__` 中接收 `**kwargs`**: Service 会将 `chunk_markdown` 接收到的所有额外参数透传给您的构造函数。即使您不使用它们，也必须接收它们以防止抛出 `TypeError`。
2.  **返回标准格式**: 确保您的 `chunk` 方法返回的列表包含至少带有 `content`、`index` 和 `type` 字段的字典。
3.  **添加测试**: 运行 `uv run pytest` (或相关测试命令) 以确保您的新策略按预期工作。
