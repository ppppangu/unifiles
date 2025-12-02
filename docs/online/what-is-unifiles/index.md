# 什么是 Unifiles

Unifiles 是一个专为大语言模型（LLM）应用设计的**文档处理基础设施平台**。它解决了构建 RAG（检索增强生成）应用时最核心的问题：**如何将各种格式的文档转化为高质量的可检索知识**。

## 核心价值主张

> Unifiles 让你专注于构建 AI 应用，而不是处理文档格式和向量存储的繁琐细节。

传统的 RAG 应用开发需要处理大量基础设施工作：文档解析、OCR 提取、文本分块、向量存储、检索优化...这些工作占用了开发者大量时间，却不直接创造业务价值。

Unifiles 将这些复杂性封装为简洁的 API，让你可以：

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 三行代码完成：上传 → 提取 → 索引
file = client.files.upload("contract.pdf")
extraction = client.extractions.create(file.id)
extraction.wait()

# 创建知识库并搜索
kb = client.knowledge_bases.create(name="legal-docs")
client.knowledge_bases.documents.create(kb.id, file.id)

results = client.knowledge_bases.search(kb.id, query="违约条款有哪些？")
```

---

## 职责分工

Unifiles 的设计理念是做一个**清晰的抽象层**——屏蔽底层复杂性，同时保留你对关键决策的控制权。

### 你的职责 vs Unifiles 的职责

<div class="grid" markdown>

| :material-account: **你负责** | :material-server: **Unifiles 负责** |
|------------------------------|-------------------------------------|
| 提供文档（PDF、Word、图片等） | 格式检测、验证和安全检查 |
| 定义知识库结构和命名 | 文档解析和 OCR 文字提取 |
| 选择分块策略（语义/固定/层级） | 执行分块算法和向量化 |
| 编写应用业务逻辑 | 向量存储和高效检索 |
| 处理搜索结果和生成回答 | 多租户数据隔离 |
| 管理 API 密钥和权限配置 | 速率限制和配额管理 |
| 配置 Webhook 接收地址 | 异步事件通知投递 |
| 自部署：准备基础设施 | 自部署：提供应用代码和配置 |

</div>

### 你保留的控制权

虽然 Unifiles 自动处理大部分复杂性，但以下关键决策仍由你掌控：

1. **分块策略**：选择 `semantic`（语义分块）、`fixed`（固定大小）或 `hierarchical`（层级分块）
2. **元数据标签**：为文档添加自定义标签，用于后续过滤检索
3. **搜索参数**：调整 `top_k`、`threshold` 等参数优化检索效果
4. **知识库结构**：按项目、部门或任意维度组织知识库

---

## 三层架构

Unifiles 将文档处理分解为三个独立的业务层，每层都可以单独使用：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 3: 知识库管理                           │
│         分块 → 向量化 → 存储 → 语义检索                          │
│         client.knowledge_bases.*                                │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 2: 内容提取                             │
│         格式转换 → OCR识别 → Markdown生成                        │
│         client.extractions.*                                    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 1: 文件管理                             │
│         上传 → 存储 → 元数据管理 → 访问控制                       │
│         client.files.*                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 按需使用

- **只需文件存储**：使用 Layer 1 API 管理文件上传和元数据
- **只需内容提取**：使用 Layer 1 + Layer 2，获取 OCR 处理后的 Markdown 内容
- **完整知识库**：使用全部三层，构建端到端的 RAG 知识检索系统

[:octicons-arrow-right-24: 了解三层架构详情](./how-it-works.md)

---

## 使用方式

Unifiles 支持多种接入方式，适应不同场景需求：

=== "Python SDK"

    最推荐的集成方式，提供类型提示和自动补全：

    ```python
    from unifiles import UnifilesClient
    
    client = UnifilesClient(api_key="sk_...")
    file = client.files.upload("document.pdf")
    ```

    [:octicons-arrow-right-24: SDK 参考](../api-reference/python-sdk/overview.md)

=== "REST API"

    适用于任何编程语言，标准 HTTP 接口：

    ```bash
    curl -X POST "https://api.unifiles.dev/v1/files" \
      -H "Authorization: Bearer sk_..." \
      -F "file=@document.pdf"
    ```

    [:octicons-arrow-right-24: API 参考](../api-reference/rest-api/overview.md)

=== "自部署"

    在你的基础设施上部署完整的 Unifiles 服务：

    ```bash
    docker-compose up -d
    ```

    [:octicons-arrow-right-24: 部署指南](../self-hosting/index.md)

---

## 典型应用场景

| 场景 | 描述 | 适用层级 |
|------|------|---------|
| **智能客服问答** | 基于产品文档的自动问答系统 | 全部三层 |
| **企业知识库** | 内部文档的智能检索和问答 | 全部三层 |
| **合同分析** | 批量提取和分析合同关键条款 | Layer 1 + 2 |
| **文档数字化** | 将扫描件转换为可搜索的文本 | Layer 1 + 2 |
| **多租户 SaaS** | 为不同客户提供隔离的知识服务 | 全部三层 |

---

## 下一步

<div class="grid cards" markdown>

-   :material-rocket-launch: **快速开始**
    
    5 分钟完成首次文件上传、内容提取和知识库检索
    
    [:octicons-arrow-right-24: quickstart.md](../quickstart.md)

-   :material-cogs: **工作原理**
    
    深入了解三层架构的技术实现
    
    [:octicons-arrow-right-24: how-it-works.md](./how-it-works.md)

-   :material-lightbulb: **设计理念**
    
    理解 Markdown-as-SSOT 和 API 设计哲学
    
    [:octicons-arrow-right-24: design-philosophy.md](./design-philosophy.md)

-   :material-scale-balance: **方案对比**
    
    与 LangChain、LlamaIndex 等方案的比较
    
    [:octicons-arrow-right-24: comparison.md](./comparison.md)

</div>
