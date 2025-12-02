# LangChain 集成

Unifiles 提供 LangChain Retriever 和 Loader 组件，可直接用于构建 RAG 应用。

## 安装

```bash
pip install unifiles langchain langchain-openai
```

## UnifilesRetriever

基于 Unifiles 知识库的 LangChain Retriever 实现。

### 基本用法

```python
from unifiles.integrations.langchain import UnifilesRetriever

# 初始化 Retriever
retriever = UnifilesRetriever(
    api_key="sk_...",
    kb_id="kb_xxx",
    top_k=5,
    threshold=0.7
)

# 检索文档
docs = retriever.get_relevant_documents("违约条款有哪些？")

for doc in docs:
    print(f"内容: {doc.page_content[:200]}...")
    print(f"来源: {doc.metadata['source']}")
    print(f"相关度: {doc.metadata['score']}")
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `api_key` | str | - | Unifiles API Key |
| `kb_id` | str | - | 知识库 ID |
| `top_k` | int | 5 | 返回的文档数量 |
| `threshold` | float | 0.0 | 相关度阈值 |
| `filter` | dict | None | 元数据过滤条件 |

### 实现源码

```python
from typing import List, Optional, Dict, Any
from langchain.schema import Document
from langchain.retrievers import BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from unifiles import UnifilesClient

class UnifilesRetriever(BaseRetriever):
    """基于 Unifiles 知识库的 LangChain Retriever"""
    
    api_key: str
    kb_id: str
    top_k: int = 5
    threshold: float = 0.0
    filter: Optional[Dict[str, Any]] = None
    
    _client: Optional[UnifilesClient] = None
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    @property
    def client(self) -> UnifilesClient:
        if self._client is None:
            self._client = UnifilesClient(api_key=self.api_key)
        return self._client
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        results = self.client.knowledge_bases.search(
            kb_id=self.kb_id,
            query=query,
            top_k=self.top_k,
            threshold=self.threshold,
            filter=self.filter
        )
        
        return [
            Document(
                page_content=chunk.content,
                metadata={
                    "source": chunk.document_id,
                    "document_title": chunk.document_title,
                    "chunk_id": chunk.id,
                    "score": chunk.score,
                    **chunk.metadata
                }
            )
            for chunk in results.chunks
        ]
```

## 构建 RAG 应用

### 基础 QA 链

```python
from unifiles.integrations.langchain import UnifilesRetriever
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

retriever = UnifilesRetriever(
    api_key="sk_unifiles_...",
    kb_id="kb_xxx",
    top_k=5
)

qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=retriever,
    return_source_documents=True
)

result = qa_chain.invoke({"query": "年假申请流程是什么？"})

print("回答:", result["result"])
print("\n来源文档:")
for doc in result["source_documents"]:
    print(f"  - {doc.metadata['document_title']}")
```

### 对话式 RAG

```python
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

conv_chain = ConversationalRetrievalChain.from_llm(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=retriever,
    memory=memory
)

# 多轮对话
response1 = conv_chain.invoke({"question": "公司有哪些福利政策？"})
print(response1["answer"])

response2 = conv_chain.invoke({"question": "年假具体是多少天？"})
print(response2["answer"])
```

### 使用 LCEL（LangChain Expression Language）

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

template = """基于以下上下文回答问题。如果上下文中没有相关信息，请说明无法回答。

上下文：
{context}

问题：{question}

回答："""

prompt = ChatPromptTemplate.from_template(template)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | ChatOpenAI(model="gpt-4")
    | StrOutputParser()
)

# 使用
answer = rag_chain.invoke("合同有效期是多久？")
print(answer)
```

### 带过滤的检索

```python
# 只检索特定类别的文档
retriever = UnifilesRetriever(
    api_key="sk_...",
    kb_id="kb_xxx",
    top_k=5,
    filter={"metadata.category": "contract"}
)

# 动态过滤
def get_filtered_retriever(department: str):
    return UnifilesRetriever(
        api_key="sk_...",
        kb_id="kb_xxx",
        filter={"metadata.department": department}
    )

hr_retriever = get_filtered_retriever("HR")
finance_retriever = get_filtered_retriever("Finance")
```

## UnifilesLoader

从 Unifiles 知识库加载所有文档。

```python
from unifiles.integrations.langchain import UnifilesLoader

loader = UnifilesLoader(
    api_key="sk_...",
    kb_id="kb_xxx"
)

# 加载所有文档
documents = loader.load()

for doc in documents:
    print(f"标题: {doc.metadata['title']}")
    print(f"内容长度: {len(doc.page_content)}")
```

### 实现源码

```python
from typing import List
from langchain.schema import Document
from unifiles import UnifilesClient

class UnifilesLoader:
    """从 Unifiles 知识库加载文档"""
    
    def __init__(self, api_key: str, kb_id: str):
        self.client = UnifilesClient(api_key=api_key)
        self.kb_id = kb_id
    
    def load(self) -> List[Document]:
        docs = self.client.knowledge_bases.documents.list(
            kb_id=self.kb_id,
            limit=1000
        )
        
        documents = []
        for doc in docs.items:
            # 获取文档的所有分块内容
            extraction = self.client.extractions.get(doc.file_id)
            
            documents.append(Document(
                page_content=extraction.markdown,
                metadata={
                    "source": doc.file_id,
                    "title": doc.title,
                    "document_id": doc.id,
                    **doc.metadata
                }
            ))
        
        return documents
```

## 高级用法

### 混合搜索 Retriever

```python
class UnifilesHybridRetriever(BaseRetriever):
    """支持混合搜索的 Retriever"""
    
    api_key: str
    kb_id: str
    top_k: int = 5
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    
    _client: Optional[UnifilesClient] = None
    
    @property
    def client(self) -> UnifilesClient:
        if self._client is None:
            self._client = UnifilesClient(api_key=self.api_key)
        return self._client
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        results = self.client.knowledge_bases.hybrid_search(
            kb_id=self.kb_id,
            query=query,
            top_k=self.top_k,
            vector_weight=self.vector_weight,
            keyword_weight=self.keyword_weight
        )
        
        return [
            Document(
                page_content=chunk.content,
                metadata={
                    "source": chunk.document_id,
                    "score": chunk.score,
                    "vector_score": chunk.vector_score,
                    "keyword_score": chunk.keyword_score
                }
            )
            for chunk in results.chunks
        ]
```

### 多知识库检索

```python
from langchain.retrievers import EnsembleRetriever

# 创建多个 Retriever
hr_retriever = UnifilesRetriever(api_key="sk_...", kb_id="kb_hr")
legal_retriever = UnifilesRetriever(api_key="sk_...", kb_id="kb_legal")
finance_retriever = UnifilesRetriever(api_key="sk_...", kb_id="kb_finance")

# 组合 Retriever
ensemble = EnsembleRetriever(
    retrievers=[hr_retriever, legal_retriever, finance_retriever],
    weights=[0.4, 0.3, 0.3]
)

# 从多个知识库检索
docs = ensemble.get_relevant_documents("报销流程")
```

### 带重排序的检索

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

# 初始化重排序模型
reranker = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
compressor = CrossEncoderReranker(model=reranker, top_n=3)

# 创建压缩 Retriever
retriever = UnifilesRetriever(
    api_key="sk_...",
    kb_id="kb_xxx",
    top_k=10  # 先检索更多，再重排序
)

compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=retriever
)

# 使用
docs = compression_retriever.get_relevant_documents("查询")
```

## 完整示例

```python
from unifiles.integrations.langchain import UnifilesRetriever
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# 配置
UNIFILES_API_KEY = "sk_..."
UNIFILES_KB_ID = "kb_xxx"
OPENAI_API_KEY = "sk_openai_..."

# 初始化组件
retriever = UnifilesRetriever(
    api_key=UNIFILES_API_KEY,
    kb_id=UNIFILES_KB_ID,
    top_k=5,
    threshold=0.7
)

llm = ChatOpenAI(
    model="gpt-4",
    api_key=OPENAI_API_KEY
)

# 定义 Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的知识库助手。基于提供的上下文准确回答问题。"),
    ("human", "上下文：\n{context}\n\n问题：{question}")
])

# 构建 RAG 链
def format_docs(docs):
    return "\n\n---\n\n".join([
        f"【{doc.metadata.get('document_title', '未知')}】\n{doc.page_content}"
        for doc in docs
    ])

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
)

# 使用
if __name__ == "__main__":
    question = "公司的年假政策是什么？"
    answer = rag_chain.invoke(question)
    print(f"问题: {question}")
    print(f"回答: {answer.content}")
```

## 下一步

- [自定义集成](custom-integration.md) - 为其他框架开发集成
- [RAG 效果评估](../cookbook/advanced/rag-evaluation.md) - 评估 RAG 效果
- [分块策略详解](../cookbook/intermediate/chunking-strategies.md) - 优化检索效果
