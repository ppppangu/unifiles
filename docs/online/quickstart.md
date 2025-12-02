# 快速开始

本指南将帮助你在 5 分钟内开始使用 Unifiles。

## 安装

```bash
pip install unifiles
```

## 获取 API 密钥

### 使用 SaaS 服务

访问 [Unifiles Console](https://console.unifiles.dev) 注册账户并获取 API 密钥。

### 自部署

参考 [自部署指南](self-hosting/index.md) 部署你自己的 Unifiles 实例。

## 初始化客户端

```python
from unifiles import UnifilesClient

# 使用 API 密钥初始化
client = UnifilesClient(api_key="[REDACTED]")

# 或使用环境变量 UNIFILES_API_KEY
client = UnifilesClient()

# 自部署时指定服务地址
client = UnifilesClient(
    api_key="[REDACTED]",
    base_url="https://your-unifiles-server.com"
)
```

## 上传文件

```python
# 上传本地文件
file = client.files.upload("document.pdf")

print(f"文件 ID: {file.id}")
print(f"文件名: {file.filename}")
print(f"大小: {file.size} bytes")

# 带元数据上传
file = client.files.upload(
    "contract.pdf",
    metadata={"department": "legal", "year": "2024"},
    tags=["contract", "important"]
)
```

## 提取内容

```python
# 创建提取任务
extraction = client.extractions.create(file_id=file.id)

# 等待完成
extraction.wait()

# 获取 Markdown 内容
print(extraction.markdown)
```

输出示例：

```markdown
# 合同标题

## 第一条 合同双方

甲方：XXX 公司
乙方：XXX 公司

## 第二条 合同内容

| 项目 | 数量 | 单价 |
|------|------|------|
| 产品A | 100 | ¥500 |
| 产品B | 200 | ¥300 |

...
```

## 创建知识库

```python
# 创建知识库
kb = client.knowledge_bases.create(
    name="company-docs",
    description="公司文档知识库"
)

print(f"知识库 ID: {kb.id}")
```

## 添加文档到知识库

```python
# 将已提取的文件添加到知识库
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id
)

# 等待索引完成
doc.wait()

print(f"文档 ID: {doc.id}")
print(f"分块数: {doc.chunk_count}")
```

## 搜索知识库

```python
# 语义搜索
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="违约责任条款",
    top_k=5
)

for chunk in results.chunks:
    print(f"相似度: {chunk.score:.3f}")
    print(f"内容: {chunk.content[:200]}...")
    print("---")
```

## 完整示例

将上述步骤组合成一个完整的流程：

```python
from unifiles import UnifilesClient

def main():
    # 初始化客户端
    client = UnifilesClient(api_key="[REDACTED]")
    
    # 1. 上传文件
    print("上传文件...")
    file = client.files.upload(
        "contract.pdf",
        metadata={"type": "contract"}
    )
    print(f"✓ 文件上传成功: {file.id}")
    
    # 2. 提取内容
    print("提取内容...")
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
    print(f"✓ 内容提取成功: {len(extraction.markdown)} 字符")
    
    # 3. 创建或获取知识库
    print("准备知识库...")
    kbs = client.knowledge_bases.list()
    kb = next((k for k in kbs if k.name == "my-kb"), None)
    if not kb:
        kb = client.knowledge_bases.create(name="my-kb")
    print(f"✓ 知识库就绪: {kb.id}")
    
    # 4. 添加文档
    print("添加文档...")
    doc = client.knowledge_bases.documents.create(
        kb_id=kb.id,
        file_id=file.id
    )
    doc.wait()
    print(f"✓ 文档已索引: {doc.chunk_count} 个分块")
    
    # 5. 搜索
    print("执行搜索...")
    results = client.knowledge_bases.search(
        kb_id=kb.id,
        query="合同期限",
        top_k=3
    )
    
    print(f"✓ 找到 {len(results.chunks)} 个相关结果:")
    for i, chunk in enumerate(results.chunks, 1):
        print(f"\n结果 {i} (相似度: {chunk.score:.3f}):")
        print(chunk.content[:200] + "...")

if __name__ == "__main__":
    main()
```

## 使用 REST API

如果你不使用 Python，可以直接调用 REST API：

### 上传文件

```bash
curl -X POST https://api.unifiles.dev/v1/files \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@document.pdf"
```

### 提取内容

```bash
curl -X POST https://api.unifiles.dev/v1/extractions \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "file_xxx"}'
```

### 搜索知识库

```bash
curl -X POST https://api.unifiles.dev/v1/knowledge-bases/kb_xxx/search \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"query": "搜索内容", "top_k": 5}'
```

## 与 LangChain 集成

```python
from unifiles.integrations.langchain import UnifilesRetriever
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA

# 创建 Retriever
retriever = UnifilesRetriever(
    api_key="[REDACTED]",
    kb_id="kb_xxx",
    top_k=5
)

# 创建 RAG Chain
llm = ChatOpenAI(model="gpt-4")
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

# 提问
result = qa_chain.invoke({"query": "合同的违约金是多少？"})
print(result["result"])
```

[查看完整 LangChain 集成指南 →](integrations/langchain.md)

## 下一步

<div class="grid cards" markdown>

-   :material-book-open-page-variant:{ .lg .middle } **了解核心概念**

    ---

    深入理解 Unifiles 的三层架构和设计理念

    [:octicons-arrow-right-24: 了解 Unifiles](what-is-unifiles/index.md)

-   :material-api:{ .lg .middle } **探索 API**

    ---

    学习 API 的完整功能和最佳实践

    [:octicons-arrow-right-24: 使用 API](using-the-api/index.md)

-   :material-book-education:{ .lg .middle } **动手实践**

    ---

    通过渐进式教程掌握各种使用场景

    [:octicons-arrow-right-24: Cookbook](cookbook/index.md)

-   :material-file-document-multiple:{ .lg .middle } **API 参考**

    ---

    查阅完整的 API 文档和类型定义

    [:octicons-arrow-right-24: API 参考](api-reference/index.md)

</div>
