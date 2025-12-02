# 方案对比

Unifiles 与其他文档处理和 RAG 方案有什么不同？本文从多个维度进行对比分析，帮助你选择最适合的方案。

## 定位差异

首先需要明确，这些方案的定位并不完全相同：

| 方案 | 定位 | 核心价值 |
|------|------|---------|
| **Unifiles** | 文档处理基础设施服务 | 开箱即用的三层文档处理 |
| **LangChain** | LLM 应用开发框架 | 灵活的组件编排能力 |
| **LlamaIndex** | 数据索引框架 | 丰富的数据连接器 |
| **Dify** | LLM 应用开发平台 | 低代码可视化搭建 |

它们可以是**互补关系**而非替代关系。例如，你可以用 Unifiles 处理文档，然后通过 LangChain 构建应用逻辑。

---

## 详细对比

### Unifiles vs 自建方案

如果你考虑自己搭建文档处理流水线：

| 维度 | 自建方案 | Unifiles |
|------|---------|----------|
| **开发时间** | 需要 2-4 周搭建基础设施 | API 调用即可使用 |
| **文档解析** | 需要集成多个解析库 | 内置多格式支持 |
| **OCR 能力** | 需要接入 OCR 服务 | 内置 OCR 引擎 |
| **向量存储** | 需要部署向量数据库 | 内置 pgvector |
| **多租户** | 需要自行设计实现 | 原生支持 |
| **运维成本** | 需要维护多个组件 | 单一服务 / 托管 |
| **灵活性** | 完全可控 | 通过配置调整 |

**适用场景**：

- 选择 **Unifiles**：快速启动，专注业务逻辑
- 选择 **自建**：有特殊定制需求，团队有足够资源

### Unifiles vs LangChain

LangChain 是一个 LLM 应用开发框架，提供了丰富的组件和链式编排能力。

| 维度 | LangChain | Unifiles |
|------|-----------|----------|
| **本质** | Python/JS 库 | 独立服务 |
| **部署方式** | 集成到你的代码中 | 独立部署或 SaaS |
| **文档处理** | 需要自行集成解析器 | 内置完整流水线 |
| **OCR** | 需要接入第三方 | 内置 |
| **向量存储** | 需要自行选择和配置 | 内置 |
| **学习曲线** | 需要理解框架概念 | API 调用 |
| **灵活性** | 极高，完全可编程 | 通过参数配置 |
| **多租户** | 需要自行实现 | 原生支持 |

**LangChain 的优势**：

- 极高的灵活性，可以组合任意组件
- 丰富的 LLM 支持（OpenAI, Claude, 本地模型等）
- 活跃的社区和生态系统
- 复杂的链式逻辑编排

**Unifiles 的优势**：

- 开箱即用，无需组装组件
- 内置文档处理能力（OCR、格式转换）
- 原生多租户支持
- 独立服务，语言无关

**搭配使用**：

```python
# Unifiles 负责文档处理
from unifiles import UnifilesClient

unifiles = UnifilesClient(api_key="sk_...")
file = unifiles.files.upload("document.pdf")
unifiles.extractions.create(file.id).wait()
unifiles.knowledge_bases.documents.create(kb_id, file.id).wait()

# LangChain 负责应用逻辑
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from unifiles.integrations.langchain import UnifilesRetriever

retriever = UnifilesRetriever(api_key="sk_...", kb_id=kb_id)
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4"),
    retriever=retriever
)

answer = qa_chain.invoke({"query": "合同的违约条款是什么？"})
```

### Unifiles vs LlamaIndex

LlamaIndex 专注于数据索引和检索，提供了丰富的数据连接器。

| 维度 | LlamaIndex | Unifiles |
|------|------------|----------|
| **本质** | Python 库 | 独立服务 |
| **数据连接器** | 100+ 数据源连接器 | 专注文档处理 |
| **文档处理** | 依赖集成的解析器 | 内置完整流水线 |
| **OCR** | 需要接入第三方 | 内置 |
| **索引策略** | 多种索引结构 | 知识库 + 分块 |
| **查询引擎** | 多种查询模式 | 语义 + 混合搜索 |
| **多租户** | 需要自行实现 | 原生支持 |

**LlamaIndex 的优势**：

- 丰富的数据源连接器（Notion, Slack, 数据库等）
- 多种索引结构（向量、关键词、图等）
- 高级查询引擎（子问题分解、路由等）

**Unifiles 的优势**：

- 内置高质量 OCR
- 文档处理即服务，无需代码集成
- 原生多租户
- 语言无关

### Unifiles vs Dify

Dify 是一个 LLM 应用开发平台，提供可视化搭建能力。

| 维度 | Dify | Unifiles |
|------|------|----------|
| **本质** | 应用开发平台 | 文档处理服务 |
| **界面** | 可视化工作流 | API / SDK |
| **文档处理** | 内置知识库 | 内置完整流水线 |
| **LLM 支持** | 多模型支持 | 不包含 LLM |
| **应用构建** | 低代码搭建 | 需要编程 |
| **部署方式** | 自部署 / 云 | 自部署 / SaaS |
| **定制性** | 中等 | 高（API 级别） |

**Dify 的优势**：

- 可视化工作流搭建
- 内置多种 LLM 支持
- 低代码，非开发者友好
- 完整的应用运行环境

**Unifiles 的优势**：

- 专注文档处理，更专业的 OCR
- API 级别集成，更灵活
- 可与任意 LLM 框架配合
- 更细粒度的控制

---

## 选择建议

### 适合选择 Unifiles 的场景

1. **需要高质量 OCR**：处理扫描件、复杂布局文档
2. **构建多租户 SaaS**：需要原生的租户隔离
3. **快速启动**：不想花时间搭建文档处理基础设施
4. **语言无关**：团队使用多种编程语言
5. **与现有系统集成**：通过 API 与现有架构对接

### 适合选择 LangChain/LlamaIndex 的场景

1. **复杂应用逻辑**：需要高度定制的链式编排
2. **多数据源**：需要连接 Notion, Slack 等数据源
3. **本地 LLM**：需要使用本地部署的模型
4. **团队熟悉 Python**：深度集成到 Python 代码库

### 组合使用

最佳实践往往是组合使用：

```
文档来源 ──► Unifiles（处理和存储）──► LangChain（应用逻辑）──► LLM ──► 用户
```

- **Unifiles** 负责文档的上传、OCR、存储和检索
- **LangChain/LlamaIndex** 负责应用逻辑和 LLM 交互

---

## 迁移指南

### 从 LangChain 迁移

如果你已经在使用 LangChain，可以逐步将文档处理迁移到 Unifiles：

```python
# 之前：LangChain + 自建文档处理
from langchain.document_loaders import PyPDFLoader
from langchain.vectorstores import Chroma

loader = PyPDFLoader("document.pdf")
docs = loader.load()
vectorstore = Chroma.from_documents(docs, embeddings)

# 之后：Unifiles + LangChain
from unifiles import UnifilesClient
from unifiles.integrations.langchain import UnifilesRetriever

client = UnifilesClient(api_key="sk_...")
file = client.files.upload("document.pdf")
client.extractions.create(file.id).wait()
client.knowledge_bases.documents.create(kb_id, file.id).wait()

retriever = UnifilesRetriever(api_key="sk_...", kb_id=kb_id)
# 后续 LangChain 代码保持不变
```

### 从自建方案迁移

1. **替换文件存储**：将文件上传改为调用 Unifiles API
2. **替换 OCR**：移除自建 OCR 逻辑，使用 Unifiles 提取
3. **替换向量存储**：使用 Unifiles 知识库
4. **适配检索接口**：使用 Unifiles 搜索 API

---

## 下一步

<div class="grid cards" markdown>

-   :material-rocket-launch: **快速开始**
    
    5 分钟体验 Unifiles
    
    [:octicons-arrow-right-24: quickstart.md](../quickstart.md)

-   :material-api: **API 使用指南**
    
    详细的 API 使用说明
    
    [:octicons-arrow-right-24: using-the-api](../using-the-api/index.md)

-   :material-link-variant: **LangChain 集成**
    
    与 LangChain 的集成指南
    
    [:octicons-arrow-right-24: langchain.md](../integrations/langchain.md)

</div>
