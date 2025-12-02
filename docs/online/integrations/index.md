# 框架集成

Unifiles 可以与主流 AI/LLM 框架无缝集成，快速构建 RAG 应用。

## 官方支持

| 框架 | 状态 | 文档 |
|-----|------|------|
| LangChain | ✅ 支持 | [LangChain 集成](langchain.md) |

## 集成方式

### 方式一：使用官方集成组件

```python
# LangChain Retriever
from unifiles.integrations.langchain import UnifilesRetriever

retriever = UnifilesRetriever(
    api_key="sk_...",
    kb_id="kb_xxx"
)

docs = retriever.get_relevant_documents("查询内容")
```

### 方式二：直接使用 SDK

```python
# 直接调用 SDK，自行构建 Document
from unifiles import UnifilesClient
from langchain.schema import Document

client = UnifilesClient(api_key="sk_...")

results = client.knowledge_bases.search(
    kb_id="kb_xxx",
    query="查询内容"
)

documents = [
    Document(
        page_content=chunk.content,
        metadata={"source": chunk.document_id, "score": chunk.score}
    )
    for chunk in results.chunks
]
```

### 方式三：自定义集成

对于其他框架，可以参考 [自定义集成指南](custom-integration.md) 实现集成。

## 快速开始

### 安装依赖

```bash
pip install unifiles langchain langchain-openai
```

### 构建 RAG 链

```python
from unifiles.integrations.langchain import UnifilesRetriever
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

# 初始化 Retriever
retriever = UnifilesRetriever(
    api_key="sk_unifiles_...",
    kb_id="kb_xxx",
    top_k=5
)

# 构建 QA 链
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=retriever,
    return_source_documents=True
)

# 提问
result = qa_chain.invoke({"query": "年假政策是什么？"})
print(result["result"])
```

## 选择集成方式

| 需求 | 推荐方式 |
|-----|---------|
| 快速构建 LangChain 应用 | 官方 LangChain 集成 |
| 需要完全控制检索逻辑 | 直接使用 SDK |
| 使用其他框架 | 自定义集成 |

## 下一步

- [LangChain 集成详解](langchain.md) - 完整的 LangChain 使用指南
- [自定义集成](custom-integration.md) - 为其他框架开发集成
