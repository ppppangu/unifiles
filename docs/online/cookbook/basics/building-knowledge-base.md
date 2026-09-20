# 构建知识库

本教程将带你创建知识库、添加文档并实现语义搜索，这是构建 RAG 应用的基础。

## 前置条件

- 已完成 [内容提取](extracting-content.md)
- 有已提取内容的文件

## 步骤 1：创建知识库

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

# 创建知识库
kb = client.knowledge_bases.create(
    name="company-docs",
    description="公司文档知识库",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)

print(f"知识库已创建: {kb.id}")
print(f"名称: {kb.name}")
print(f"分块策略: {kb.chunking_strategy}")
```

**输出：**

```
知识库已创建: kb_abc123
名称: company-docs
分块策略: {'type': 'semantic', 'chunk_size': 512, 'overlap': 50}
```

## 步骤 2：添加文档

```python
# 假设已有提取完成的文件
file = client.files.upload("handbook.pdf")
extraction = client.extractions.create(file_id=file.id)
extraction.wait()

# 将文件添加到知识库
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id,
    title="员工手册 2024",
    metadata={
        "category": "HR",
        "version": "2024.1"
    }
)

print(f"文档已添加: {doc.id}")
print(f"状态: {doc.status}")  # pending -> indexing -> indexed
```

## 步骤 3：等待索引完成

```python
# 等待索引完成
doc = doc.wait(timeout=300)

if doc.status == "indexed":
    print(f"索引完成！")
    print(f"分块数量: {doc.chunk_count}")
else:
    print(f"索引失败: {doc.error}")
```

**输出：**

```
索引完成！
分块数量: 42
```

## 步骤 4：语义搜索

```python
# 搜索
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="年假申请流程是什么？",
    top_k=5
)

print(f"找到 {len(results.chunks)} 个相关片段\n")

for i, chunk in enumerate(results.chunks, 1):
    print(f"--- 结果 {i} (相关度: {chunk.score:.2f}) ---")
    print(f"来源: {chunk.document_title}")
    print(f"内容: {chunk.content[:200]}...")
    print()
```

**输出：**

```
找到 5 个相关片段

--- 结果 1 (相关度: 0.92) ---
来源: 员工手册 2024
内容: ## 年假申请流程

1. 登录 HR 系统
2. 选择"假期申请"
3. 填写年假天数和日期
4. 提交给直属主管审批
5. 等待审批结果（通常1-2个工作日）...

--- 结果 2 (相关度: 0.85) ---
来源: 员工手册 2024
内容: ### 年假计算方式

员工入职满一年后，每年享有5天带薪年假。工龄每增加一年，年假增加1天，最高不超过15天...
```

## 步骤 5：使用搜索结果

### 构建 RAG 上下文

```python
from openai import OpenAI

openai = OpenAI(api_key="<openai-api-key>")

def answer_question(kb_id: str, question: str) -> str:
    """基于知识库回答问题"""
    
    # 1. 检索相关内容
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=question,
        top_k=5
    )
    
    # 2. 构建上下文
    context = "\n\n".join([
        f"【{chunk.document_title}】\n{chunk.content}"
        for chunk in results.chunks
    ])
    
    # 3. 调用 LLM
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "你是一个知识库助手。基于提供的上下文回答问题。如果上下文中没有相关信息，请说明无法回答。"
            },
            {
                "role": "user",
                "content": f"上下文：\n{context}\n\n问题：{question}"
            }
        ]
    )
    
    return response.choices[0].message.content

# 使用
answer = answer_question(kb.id, "年假申请流程是什么？")
print(answer)
```

## 完整工作流示例

```python
from unifiles import UnifilesClient

def build_knowledge_base(name: str, file_paths: list) -> str:
    """构建知识库的完整流程"""
    
    client = UnifilesClient(api_key="<api-key>")
    
    # 1. 创建知识库
    print(f"创建知识库: {name}")
    kb = client.knowledge_bases.create(
        name=name,
        chunking_strategy={
            "type": "semantic",
            "chunk_size": 512,
            "overlap": 50
        }
    )
    print(f"✓ 知识库ID: {kb.id}")
    
    # 2. 处理每个文件
    for path in file_paths:
        print(f"\n处理文件: {path}")
        
        # 上传
        file = client.files.upload(path)
        print(f"  ✓ 上传完成: {file.id}")
        
        # 提取
        extraction = client.extractions.create(file_id=file.id)
        extraction.wait()
        print(f"  ✓ 提取完成: {extraction.total_pages} 页")
        
        # 索引
        doc = client.knowledge_bases.documents.create(
            kb_id=kb.id,
            file_id=file.id
        )
        doc.wait()
        print(f"  ✓ 索引完成: {doc.chunk_count} 个分块")
    
    # 3. 显示统计
    kb = client.knowledge_bases.get(kb.id)
    print(f"\n知识库构建完成！")
    print(f"  文档数: {kb.document_count}")
    print(f"  分块数: {kb.chunk_count}")
    
    return kb.id

# 使用
kb_id = build_knowledge_base(
    name="hr-knowledge",
    file_paths=[
        "handbook.pdf",
        "policies.docx",
        "faq.md"
    ]
)

# 搜索测试
results = client.knowledge_bases.search(
    kb_id=kb_id,
    query="如何申请报销？"
)
```

## 分块策略选择

### semantic（语义分块）- 推荐

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    }
)
```

基于语义边界智能切分，保持内容完整性。

### fixed（固定大小分块）

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "fixed",
        "chunk_size": 512,
        "overlap": 50
    }
)
```

按固定 token 数切分，简单高效。

### paragraph（段落分块）

```python
kb = client.knowledge_bases.create(
    name="my-kb",
    chunking_strategy={
        "type": "paragraph",
        "max_chunk_size": 1024,
        "min_chunk_size": 100
    }
)
```

按段落边界切分，保持段落完整。

## 搜索技巧

### 调整 top_k

```python
# 精确问答：较少结果
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="公司地址",
    top_k=3
)

# 综合分析：更多结果
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="总结福利政策",
    top_k=10
)
```

### 使用阈值过滤

```python
# 只要高相关的结果
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="年假政策",
    threshold=0.8  # 相关度 >= 0.8
)
```

### 混合搜索

```python
# 结合语义和关键词
results = client.knowledge_bases.hybrid_search(
    kb_id=kb.id,
    query="ISO9001认证要求",
    vector_weight=0.6,  # 语义权重
    keyword_weight=0.4  # 关键词权重
)
```

### 元数据过滤

```python
# 只搜索特定类别的文档
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="报销流程",
    filter={"metadata.category": "财务"}
)
```

## 管理知识库

### 查看知识库状态

```python
kb = client.knowledge_bases.get(kb_id)

print(f"名称: {kb.name}")
print(f"文档数: {kb.document_count}")
print(f"分块数: {kb.chunk_count}")
print(f"创建时间: {kb.created_at}")
```

### 列出文档

```python
docs = client.knowledge_bases.documents.list(kb_id=kb.id)

for doc in docs.items:
    print(f"{doc.id}: {doc.title} ({doc.chunk_count} chunks)")
```

### 删除文档

```python
# 从知识库移除文档（不删除原文件）
client.knowledge_bases.documents.delete(
    kb_id=kb.id,
    document_id=doc.id
)
```

### 删除知识库

```python
# 删除整个知识库（包括所有文档和分块）
client.knowledge_bases.delete(kb_id)
```

## 常见问题

### Q: 同一文件可以加入多个知识库吗？

**A:** 可以。同一文件可以使用不同的分块策略加入不同知识库。

```python
# 细粒度知识库
kb_qa = client.knowledge_bases.create(
    name="qa-kb",
    chunking_strategy={"type": "fixed", "chunk_size": 256}
)
client.knowledge_bases.documents.create(kb_id=kb_qa.id, file_id=file.id)

# 大分块知识库
kb_summary = client.knowledge_bases.create(
    name="summary-kb",
    chunking_strategy={"type": "semantic", "chunk_size": 1024}
)
client.knowledge_bases.documents.create(kb_id=kb_summary.id, file_id=file.id)
```

### Q: 如何更新知识库中的文档？

**A:** 删除旧文档，添加新文档。

```python
# 删除旧版本
client.knowledge_bases.documents.delete(kb_id, old_doc_id)

# 上传新版本
new_file = client.files.upload("handbook_v2.pdf")
extraction = client.extractions.create(file_id=new_file.id)
extraction.wait()

# 添加新文档
new_doc = client.knowledge_bases.documents.create(
    kb_id=kb_id,
    file_id=new_file.id,
    title="员工手册 v2.0"
)
```

### Q: 搜索结果不准确怎么办？

**A:** 尝试以下优化：

1. 调整分块策略（更小或更大的 chunk_size）
2. 使用混合搜索增加召回率
3. 调整 threshold 过滤低质量结果
4. 优化查询语句

## 下一步

知识库构建完成后，你可以：

- [分块策略详解](../intermediate/chunking-strategies.md) - 优化分块提升搜索效果
- [LangChain 集成](../../integrations/langchain.md) - 将知识库接入 LangChain
- [RAG 效果评估](../advanced/rag-evaluation.md) - 评估和优化 RAG 效果
