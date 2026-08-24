# Cookbook

欢迎来到 Unifiles Cookbook！这是一系列渐进式教程，从基础概念到高级应用，帮助你逐步掌握 Unifiles 的全部能力。

## 学习路径

```
基础概念 → 入门操作 → 进阶技巧 → 高级应用
   │           │           │          │
   ▼           ▼           ▼          ▼
 理解输出    上传文件    分块策略   多租户配置
 三层架构    内容提取    元数据     自定义OCR
            知识库      Webhook    性能调优
                       批量处理    RAG评估
```

## 基础概念 (Foundational)

在开始实际操作之前，先了解 Unifiles 的核心概念：

| 教程 | 说明 | 时长 |
|-----|------|------|
| [理解 Markdown 输出](foundational/understanding-output.md) | 为什么选择 Markdown？如何利用结构化输出 | 10分钟 |
| [三层架构入门](foundational/three-layers-primer.md) | 文件、提取、知识库三层的协作方式 | 15分钟 |

## 入门操作 (Basics)

动手实践基本操作：

| 教程 | 说明 | 时长 |
|-----|------|------|
| [第一次上传](basics/your-first-upload.md) | 上传第一个文件，了解文件生命周期 | 10分钟 |
| [内容提取](basics/extracting-content.md) | 从各种文档中提取结构化内容 | 15分钟 |
| [构建知识库](basics/building-knowledge-base.md) | 创建知识库并实现语义搜索 | 20分钟 |

## 进阶技巧 (Intermediate)

掌握更高效的使用方式：

| 教程 | 说明 | 时长 |
|-----|------|------|
| [分块策略详解](intermediate/chunking-strategies.md) | 选择和优化分块策略以提升检索效果 | 25分钟 |
| [元数据与标签](intermediate/custom-metadata.md) | 利用元数据实现精细化管理和过滤 | 15分钟 |
| [Webhook 集成](intermediate/webhook-integration.md) | 构建事件驱动的异步处理流程 | 20分钟 |
| [批量处理](intermediate/batch-processing.md) | 高效处理大量文件的最佳实践 | 25分钟 |

## 高级应用 (Advanced)

面向生产环境的高级主题：

| 教程 | 说明 | 时长 |
|-----|------|------|
| [多租户配置](advanced/multi-tenant-setup.md) | 为多个客户/项目实现数据隔离 | 30分钟 |
| [自定义 OCR](advanced/custom-ocr-providers.md) | 集成自定义 OCR 提供者 | 25分钟 |
| [性能调优](advanced/performance-tuning.md) | 优化大规模部署的性能 | 30分钟 |
| [RAG 效果评估](advanced/rag-evaluation.md) | 评估和优化检索增强生成效果 | 35分钟 |

## 前置条件

在开始之前，请确保：

1. **已安装 SDK**
   ```bash
   pip install unifiles-client
   ```

2. **已获取 API Key**
   ```python
   from unifiles import UnifilesClient
   client = UnifilesClient(api_key="sk_...")
   ```

3. **准备测试文件**
   - 一个 PDF 文件（用于基础教程）
   - 多个文档（用于进阶教程）

## 推荐学习顺序

### 快速入门（约1小时）

如果你想快速上手：

1. [三层架构入门](foundational/three-layers-primer.md) - 理解核心概念
2. [第一次上传](basics/your-first-upload.md) - 动手实践
3. [构建知识库](basics/building-knowledge-base.md) - 实现搜索

### 完整学习（约4小时）

如果你想全面掌握：

1. 按顺序完成 Foundational → Basics → Intermediate
2. 根据需要选择 Advanced 主题

### 特定场景

**我需要处理大量文档：**
1. [批量处理](intermediate/batch-processing.md)
2. [Webhook 集成](intermediate/webhook-integration.md)
3. [性能调优](advanced/performance-tuning.md)

**我需要构建高质量 RAG 应用：**
1. [分块策略详解](intermediate/chunking-strategies.md)
2. [元数据与标签](intermediate/custom-metadata.md)
3. [RAG 效果评估](advanced/rag-evaluation.md)

**我需要支持多个客户：**
1. [多租户配置](advanced/multi-tenant-setup.md)
2. [元数据与标签](intermediate/custom-metadata.md)

## 代码约定

所有教程中的代码示例遵循以下约定：

```python
# 导入
from unifiles import UnifilesClient

# 初始化（假设 API Key 已配置）
client = UnifilesClient(api_key="sk_...")

# 变量命名
file = client.files.upload(...)        # 单个文件
files = client.files.list(...)         # 文件列表
kb = client.knowledge_bases.create(...) # 知识库
doc = client.knowledge_bases.documents.create(...)  # 文档
```

## 获取帮助

- **API 参考**：[REST API](../api-reference/rest-api/overview.md) | [Python SDK](../api-reference/python-sdk/overview.md)
- **概念解释**：[设计理念](../what-is-unifiles/design-philosophy.md)
- **问题排查**：[错误处理](../using-the-api/error-handling.md)

---

准备好了吗？从 [理解 Markdown 输出](foundational/understanding-output.md) 开始你的学习之旅！
