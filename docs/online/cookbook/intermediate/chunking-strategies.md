# 分块策略详解

分块策略直接影响 RAG 的检索效果。本教程深入讲解各种分块策略的原理、适用场景和优化技巧。

## 为什么分块很重要？

### 问题：分块不当的影响

```
分块太小：
├── 语义不完整
├── 上下文丢失
└── 需要检索更多块才能获得完整信息

分块太大：
├── 包含无关信息
├── 降低检索精度
└── 浪费 LLM token
```

### 目标：找到平衡点

```
理想的分块 = 语义完整 + 聚焦主题 + 适当长度
```

## 三种分块策略

### 1. fixed（固定大小分块）

按固定 token 数切分文档。

```python
kb = client.knowledge_bases.create(
    name="fixed-chunks",
    chunking_strategy={
        "type": "fixed",
        "chunk_size": 512,      # 每块 512 tokens
        "overlap": 50           # 相邻块重叠 50 tokens
    }
)
```

**工作原理：**

```
原文：AAAAA BBBBB CCCCC DDDDD EEEEE FFFFF

chunk_size=5, overlap=1:
├── Chunk 1: AAAAA B
├── Chunk 2: B BBBBB C    (B 是重叠部分)
├── Chunk 3: C CCCCC D
├── Chunk 4: D DDDDD E
└── Chunk 5: E EEEEE F
```

**优点：**
- 处理速度最快
- 分块大小可预测
- 实现简单

**缺点：**
- 可能在句子中间切分
- 语义完整性差

**适用场景：**
- 结构不规则的文档
- 对速度要求高
- 大规模初始索引

### 2. semantic（语义分块）

基于语义边界智能切分。

```python
kb = client.knowledge_bases.create(
    name="semantic-chunks",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,      # 目标大小
        "overlap": 50           # 重叠大小
    }
)
```

**工作原理：**

```
原文（Markdown）:
# 第一章
第一章内容...

## 1.1 小节
小节内容很长很长...

# 第二章
第二章内容...

语义分块结果:
├── Chunk 1: "# 第一章\n第一章内容..."
├── Chunk 2: "## 1.1 小节\n小节内容前半部分..."
├── Chunk 3: "小节内容后半部分..."（超过 chunk_size 时切分）
└── Chunk 4: "# 第二章\n第二章内容..."
```

**优点：**
- 保持语义完整性
- 尊重文档结构
- 检索效果最好

**缺点：**
- 处理速度较慢
- 分块大小不均匀

**适用场景：**
- 结构化文档（合同、论文、手册）
- 对搜索质量要求高
- RAG 问答系统

### 3. paragraph（段落分块）

按段落边界切分。

```python
kb = client.knowledge_bases.create(
    name="paragraph-chunks",
    chunking_strategy={
        "type": "paragraph",
        "max_chunk_size": 1024,   # 最大块大小
        "min_chunk_size": 100     # 最小块大小
    }
)
```

**工作原理：**

```
原文:
段落1内容...

段落2内容（很长）...

段落3内容...

段落分块结果:
├── Chunk 1: "段落1内容..."
├── Chunk 2: "段落2前半部分..."（超过 max 时切分）
├── Chunk 3: "段落2后半部分..."
└── Chunk 4: "段落3内容..."

注：太短的段落可能合并（< min_chunk_size）
```

**优点：**
- 保持段落完整
- 处理速度快
- 适合格式一致的文档

**缺点：**
- 段落长度差异大
- 可能产生很小或很大的块

**适用场景：**
- 格式规范的文档
- 段落结构清晰
- 文章、博客类内容

## 参数调优指南

### chunk_size 选择

```python
# 小分块：适合精确问答
chunking_strategy = {
    "type": "semantic",
    "chunk_size": 256,  # 小块，更精确
    "overlap": 30
}

# 中等分块：通用场景
chunking_strategy = {
    "type": "semantic", 
    "chunk_size": 512,  # 平衡大小
    "overlap": 50
}

# 大分块：适合摘要、总结
chunking_strategy = {
    "type": "semantic",
    "chunk_size": 1024,  # 大块，更多上下文
    "overlap": 100
}
```

**选择依据：**

| chunk_size | 适用场景 | 示例问题 |
|------------|---------|---------|
| 128-256 | 精确事实查询 | "公司注册日期是？" |
| 256-512 | 概念解释 | "什么是年假？" |
| 512-1024 | 流程说明 | "如何申请报销？" |
| 1024+ | 综合分析 | "总结福利政策" |

### overlap 选择

重叠确保跨块的内容不丢失。

```python
# 通常设置为 chunk_size 的 10-20%
chunk_size = 512
overlap = 50  # ~10%
```

**重叠的作用：**

```
无重叠：
Chunk 1: "...违约金按照合同金额的"
Chunk 2: "10%计算，最高不超过..."
问题：搜索"违约金计算"可能找不到完整答案

有重叠：
Chunk 1: "...违约金按照合同金额的10%计算"
Chunk 2: "合同金额的10%计算，最高不超过..."
好处：两个块都包含关键信息
```

## 实战：对比分块效果

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

# 准备测试文件
file = client.files.upload("handbook.pdf")
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 创建三个知识库，使用不同策略
strategies = [
    {"name": "fixed-256", "type": "fixed", "chunk_size": 256, "overlap": 25},
    {"name": "semantic-512", "type": "semantic", "chunk_size": 512, "overlap": 50},
    {"name": "semantic-1024", "type": "semantic", "chunk_size": 1024, "overlap": 100}
]

kbs = {}
for s in strategies:
    kb = client.knowledge_bases.create(
        name=s["name"],
        chunking_strategy={
            "type": s["type"],
            "chunk_size": s["chunk_size"],
            "overlap": s["overlap"]
        }
    )
    doc = client.knowledge_bases.documents.create(
        kb_id=kb.id,
        file_id=file.id
    )
    doc.wait()
    kbs[s["name"]] = kb
    print(f"{s['name']}: {doc.chunk_count} chunks")

# 测试查询
test_queries = [
    "公司注册资本是多少？",          # 精确查询
    "年假申请流程是什么？",          # 流程查询
    "总结员工福利政策",              # 综合查询
]

for query in test_queries:
    print(f"\n查询: {query}")
    print("-" * 50)
    
    for name, kb in kbs.items():
        results = client.knowledge_bases.search(
            kb_id=kb.id,
            query=query,
            top_k=1
        )
        if results.chunks:
            chunk = results.chunks[0]
            print(f"\n{name} (score: {chunk.score:.2f}):")
            print(f"  {chunk.content[:150]}...")
```

## 特定场景的最佳实践

### 场景1：FAQ 问答系统

```python
# FAQ 通常是独立的问答对，使用小分块
kb = client.knowledge_bases.create(
    name="faq-kb",
    chunking_strategy={
        "type": "paragraph",       # 按段落/QA对分块
        "max_chunk_size": 256,     # 小块
        "min_chunk_size": 50
    }
)
```

### 场景2：法律合同分析

```python
# 合同条款需要保持完整
kb = client.knowledge_bases.create(
    name="legal-kb",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 1024,        # 大块保持条款完整
        "overlap": 100
    }
)
```

### 场景3：技术文档

```python
# 技术文档有清晰的层级结构
kb = client.knowledge_bases.create(
    name="tech-docs-kb",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)
```

### 场景4：客服对话记录

```python
# 对话轮次相对独立
kb = client.knowledge_bases.create(
    name="support-kb",
    chunking_strategy={
        "type": "paragraph",
        "max_chunk_size": 512,
        "min_chunk_size": 100
    }
)
```

## 高级技巧

### 1. 同一文档使用多种分块

```python
# 文档同时加入两个知识库
file = client.files.upload("policy.pdf")
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 精确查询用小分块
kb_precise = client.knowledge_bases.create(
    name="precise",
    chunking_strategy={"type": "fixed", "chunk_size": 256, "overlap": 25}
)
client.knowledge_bases.documents.create(kb_id=kb_precise.id, file_id=file.id)

# 综合分析用大分块
kb_context = client.knowledge_bases.create(
    name="context",
    chunking_strategy={"type": "semantic", "chunk_size": 1024, "overlap": 100}
)
client.knowledge_bases.documents.create(kb_id=kb_context.id, file_id=file.id)

# 根据查询类型选择知识库
def smart_search(query: str, is_factual: bool = True):
    kb_id = kb_precise.id if is_factual else kb_context.id
    return client.knowledge_bases.search(kb_id=kb_id, query=query)
```

### 2. 结合元数据增强检索

```python
# 分块时保留章节信息
kb = client.knowledge_bases.create(
    name="enhanced-kb",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50,
        "include_headers": True  # 在分块中包含章节标题
    }
)

# 搜索时过滤特定章节
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="申请流程",
    filter={"metadata.section": "人事政策"}
)
```

### 3. 动态调整策略

```python
def adaptive_search(kb_id: str, query: str):
    """根据初次搜索结果动态调整"""
    
    # 第一次搜索
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=5
    )
    
    # 如果最高分很低，可能需要更多上下文
    if results.chunks and results.chunks[0].score < 0.7:
        # 尝试获取相邻块
        chunk = results.chunks[0]
        # 获取前后文（如果API支持）
        pass
    
    return results
```

## 分块策略对比表

| 特性 | fixed | semantic | paragraph |
|-----|-------|----------|-----------|
| 处理速度 | 最快 | 中等 | 快 |
| 语义完整性 | 低 | 高 | 中 |
| 分块均匀度 | 高 | 低 | 中 |
| 适合文档类型 | 任意 | 结构化 | 段落清晰 |
| 推荐场景 | 大规模索引 | RAG问答 | 文章/博客 |

## 下一步

- [元数据与标签](custom-metadata.md) - 利用元数据增强检索
- [RAG 效果评估](../advanced/rag-evaluation.md) - 评估分块策略效果
- [性能调优](../advanced/performance-tuning.md) - 大规模知识库优化
