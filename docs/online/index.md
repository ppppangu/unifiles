# Unifiles

**LLM 应用层的文档处理基础设施**

Unifiles 是一个自托管的文档处理平台，为 AI 应用提供文件存储、内容提取和知识库管理的完整解决方案。

## 为什么选择 Unifiles？

<div class="grid cards" markdown>

-   :material-layers-triple:{ .lg .middle } **三层解耦架构**

    ---

    文件存储、内容提取、知识库管理完全解耦，灵活组合满足不同场景需求

    [:octicons-arrow-right-24: 了解架构](what-is-unifiles/how-it-works.md)

-   :material-file-document:{ .lg .middle } **Markdown 即真相**

    ---

    统一的 Markdown 输出格式，消除格式碎片化，简化下游处理逻辑

    [:octicons-arrow-right-24: 了解更多](what-is-unifiles/design-philosophy.md)

-   :material-api:{ .lg .middle } **简洁的 API**

    ---

    类 Stripe 的命名空间化 SDK 设计，几行代码完成复杂的文档处理流程

    [:octicons-arrow-right-24: 查看 API](api-reference/index.md)

-   :material-server:{ .lg .middle } **完全自托管**

    ---

    数据完全由你控制，支持 Docker Compose 和 Kubernetes 部署

    [:octicons-arrow-right-24: 部署指南](self-hosting/index.md)

</div>

## 快速体验

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 上传文件
file = client.files.upload("contract.pdf")

# 提取内容
extraction = client.extractions.create(file_id=file.id)
extraction.wait()
print(extraction.markdown)  # Markdown 格式的内容

# 创建知识库并搜索
kb = client.knowledge_bases.create(name="contracts")
client.knowledge_bases.documents.create(kb_id=kb.id, file_id=file.id)

results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="违约条款"
)
```

[:octicons-arrow-right-24: 完整快速开始指南](quickstart.md)

## 核心功能

### Layer 1: 文件存储

安全存储各种格式的文档，支持去重、元数据和标签管理。

```python
file = client.files.upload(
    "document.pdf",
    metadata={"project": "Q4-review"},
    tags=["finance", "quarterly"]
)
```

### Layer 2: 内容提取

将 PDF、Word、Excel 等格式转换为结构化的 Markdown。

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",  # 高精度 OCR
    options={"extract_tables": True}
)
```

### Layer 3: 知识库

构建向量知识库，支持语义搜索和混合搜索。

```python
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="关键条款",
    search_type="hybrid",
    top_k=10
)
```

## 集成生态

<div class="grid cards" markdown>

-   :simple-langchain:{ .lg .middle } **LangChain**

    ---

    原生 Retriever 和 Loader 支持，无缝集成 RAG 流程

    [:octicons-arrow-right-24: LangChain 集成](integrations/langchain.md)

-   :material-webhook:{ .lg .middle } **Webhooks**

    ---

    事件驱动的处理通知，构建响应式应用

    [:octicons-arrow-right-24: Webhook 指南](using-the-api/webhooks.md)

</div>

## 文档导航

| 我想要... | 去这里 |
|----------|-------|
| 快速了解 Unifiles | [快速开始](quickstart.md) |
| 理解核心概念 | [了解 Unifiles](what-is-unifiles/index.md) |
| 学习 API 使用 | [使用 API](using-the-api/index.md) |
| 参考代码示例 | [Cookbook](cookbook/index.md) |
| 查找 API 细节 | [API 参考](api-reference/index.md) |
| 部署到生产 | [自部署指南](self-hosting/index.md) |

## 获取帮助

- [GitHub Issues](https://github.com/ppppangu/Unifiles/issues) - 报告问题
- [GitHub Discussions](https://github.com/ppppangu/Unifiles/discussions) - 社区讨论
- [故障排除](self-hosting/troubleshooting.md) - 常见问题解决

## 开源协议

Unifiles 采用 [Apache 2.0](https://github.com/ppppangu/Unifiles/blob/main/LICENSE) 开源协议。
