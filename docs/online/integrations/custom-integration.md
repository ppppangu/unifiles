# 自定义集成

本指南介绍如何为其他框架或自定义应用实现 Unifiles 集成。

## 集成模式

### 模式一：直接使用 SDK

最简单的方式，适用于任何 Python 应用：

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

def search_knowledge_base(query: str, kb_id: str) -> list:
    """搜索知识库并返回结果"""
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=5
    )
    
    return [
        {
            "content": chunk.content,
            "source": chunk.document_title,
            "score": chunk.score,
            "metadata": chunk.metadata
        }
        for chunk in results.chunks
    ]

# 在你的应用中使用
results = search_knowledge_base("年假政策", "kb_xxx")
for r in results:
    print(f"[{r['score']:.2f}] {r['content'][:100]}...")
```

### 模式二：封装为 Retriever 接口

为框架提供统一的检索接口：

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class RetrievedDocument:
    """检索结果文档"""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]

class BaseRetriever(ABC):
    """Retriever 基类"""
    
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        pass

class UnifilesRetriever(BaseRetriever):
    """Unifiles Retriever 实现"""
    
    def __init__(self, api_key: str, kb_id: str, threshold: float = 0.0):
        self.client = UnifilesClient(api_key=api_key)
        self.kb_id = kb_id
        self.threshold = threshold
    
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        results = self.client.knowledge_bases.search(
            kb_id=self.kb_id,
            query=query,
            top_k=top_k,
            threshold=self.threshold
        )
        
        return [
            RetrievedDocument(
                content=chunk.content,
                source=chunk.document_title,
                score=chunk.score,
                metadata=chunk.metadata
            )
            for chunk in results.chunks
        ]
```

### 模式三：REST API 直接调用

适用于非 Python 语言：

```javascript
// JavaScript 示例
async function searchKnowledgeBase(query, kbId) {
    const response = await fetch(
        `https://api.unifiles.dev/v1/knowledge-bases/${kbId}/search`,
        {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${API_KEY}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                top_k: 5,
                threshold: 0.7
            })
        }
    );
    
    const data = await response.json();
    return data.chunks;
}
```

## 完整 RAG 实现示例

### 无框架的纯 Python RAG

```python
from unifiles import UnifilesClient
from openai import OpenAI

class SimpleRAG:
    """简单的 RAG 实现"""
    
    def __init__(
        self,
        unifiles_api_key: str,
        openai_api_key: str,
        kb_id: str
    ):
        self.unifiles = UnifilesClient(api_key=unifiles_api_key)
        self.openai = OpenAI(api_key=openai_api_key)
        self.kb_id = kb_id
    
    def retrieve(self, query: str, top_k: int = 5) -> str:
        """检索相关内容"""
        results = self.unifiles.knowledge_bases.search(
            kb_id=self.kb_id,
            query=query,
            top_k=top_k
        )
        
        context = "\n\n---\n\n".join([
            f"【{chunk.document_title}】\n{chunk.content}"
            for chunk in results.chunks
        ])
        
        return context
    
    def generate(self, query: str, context: str) -> str:
        """生成回答"""
        response = self.openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个知识库助手。基于提供的上下文回答问题。如果上下文中没有相关信息，请说明无法回答。"
                },
                {
                    "role": "user",
                    "content": f"上下文：\n{context}\n\n问题：{query}"
                }
            ]
        )
        return response.choices[0].message.content
    
    def ask(self, query: str) -> dict:
        """完整的问答流程"""
        context = self.retrieve(query)
        answer = self.generate(query, context)
        return {
            "query": query,
            "answer": answer,
            "context": context
        }

# 使用
rag = SimpleRAG(
    unifiles_api_key="sk_unifiles_...",
    openai_api_key="sk_openai_...",
    kb_id="kb_xxx"
)

result = rag.ask("年假申请流程是什么？")
print(result["answer"])
```

### FastAPI 集成

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from unifiles import UnifilesClient

app = FastAPI()
client = UnifilesClient(api_key="sk_...")

class SearchRequest(BaseModel):
    query: str
    kb_id: str
    top_k: int = 5

class SearchResponse(BaseModel):
    query: str
    results: list

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        results = client.knowledge_bases.search(
            kb_id=request.kb_id,
            query=request.query,
            top_k=request.top_k
        )
        
        return SearchResponse(
            query=request.query,
            results=[
                {
                    "content": chunk.content,
                    "source": chunk.document_title,
                    "score": chunk.score
                }
                for chunk in results.chunks
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Streamlit 应用

```python
import streamlit as st
from unifiles import UnifilesClient
from openai import OpenAI

st.title("知识库问答")

# 初始化客户端
@st.cache_resource
def get_clients():
    return (
        UnifilesClient(api_key=st.secrets["UNIFILES_API_KEY"]),
        OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    )

unifiles, openai_client = get_clients()

# 输入
query = st.text_input("请输入问题：")
kb_id = st.selectbox("选择知识库", ["kb_hr", "kb_legal", "kb_finance"])

if st.button("搜索") and query:
    with st.spinner("检索中..."):
        # 检索
        results = unifiles.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            top_k=5
        )
        
        context = "\n\n".join([c.content for c in results.chunks])
        
        # 生成
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "基于上下文回答问题。"},
                {"role": "user", "content": f"上下文：{context}\n\n问题：{query}"}
            ]
        )
        
        st.subheader("回答")
        st.write(response.choices[0].message.content)
        
        st.subheader("参考来源")
        for chunk in results.chunks:
            with st.expander(f"{chunk.document_title} (相关度: {chunk.score:.2f})"):
                st.write(chunk.content)
```

## 最佳实践

### 1. 错误处理

```python
from unifiles.exceptions import UnifilesError, RateLimitError

def safe_search(query: str, kb_id: str):
    try:
        return client.knowledge_bases.search(kb_id=kb_id, query=query)
    except RateLimitError as e:
        # 处理速率限制
        time.sleep(e.retry_after)
        return safe_search(query, kb_id)
    except UnifilesError as e:
        # 记录错误
        logger.error(f"搜索失败: {e.message}")
        return None
```

### 2. 结果缓存

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_search(kb_id: str, query: str, top_k: int) -> tuple:
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=top_k
    )
    # 转为可哈希的元组
    return tuple(
        (c.content, c.score, c.document_title)
        for c in results.chunks
    )
```

### 3. 异步支持

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=5)

async def async_search(query: str, kb_id: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        lambda: client.knowledge_bases.search(kb_id=kb_id, query=query)
    )
```

## 下一步

- [LangChain 集成](langchain.md) - 官方 LangChain 支持
- [API 参考](../api-reference/index.md) - 完整 API 文档
- [RAG 效果评估](../cookbook/advanced/rag-evaluation.md) - 评估集成效果
