# 框架集成

Unifiles 可以通过 SDK 和 HTTP API 接入 AI/LLM 框架，构建 RAG 应用。

!!! warning "当前发布范围"
    当前 `unifiles-client` 不发布 `unifiles.integrations.langchain` 模块。LangChain
    页面中的 Retriever/Loader 是设计示例，不是可以直接导入的官方包；生产代码请使用
    `UnifilesClient` 查询知识库，再转换成你所用 LangChain 版本的 `Document`。

## 官方支持

| 框架 | 状态 | 文档 |
|-----|------|------|
| LangChain | 通过 SDK/API 自定义 | [LangChain 集成](langchain.md) |

## 集成方式

### 方式一：使用 SDK 适配 LangChain

```python
# 查询知识库，再映射到 LangChain Document
from unifiles import UnifilesClient
from langchain_core.documents import Document

client = UnifilesClient(api_key="<api-key>")
results = client.knowledge_bases.search(kb_id="kb_xxx", query="查询内容")
docs = [
    Document(page_content=chunk.content, metadata={"source": chunk.document_id})
    for chunk in results.chunks
]
```

### 方式二：直接使用 SDK

```python
# 直接调用 SDK，自行构建 Document
from unifiles import UnifilesClient
from langchain.schema import Document

client = UnifilesClient(api_key="<api-key>")

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
pip install unifiles-client langchain langchain-openai
```

### 构建 RAG 链

```python
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from unifiles import UnifilesClient

# 查询 Unifiles，再把结果转换为当前 LangChain 版本的 Document/retriever
client = UnifilesClient(api_key="<api-key>")
results = client.knowledge_bases.search("kb_xxx", "年假政策是什么？", top_k=5)

# 构建 QA 链
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=your_langchain_retriever,
    return_source_documents=True
)

# 提问
result = qa_chain.invoke({"query": "年假政策是什么？"})
print(result["result"])
```

## 选择集成方式

| 需求 | 推荐方式 |
|-----|---------|
| 快速构建 LangChain 应用 | SDK 查询后映射为 `Document` |
| 需要完全控制检索逻辑 | 直接使用 SDK |
| 使用其他框架 | 自定义集成 |

## 下一步

- [LangChain 集成详解](langchain.md) - 当前能力边界与适配示例
- [自定义集成](custom-integration.md) - 为其他框架开发集成
