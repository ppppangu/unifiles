# 📚 File Server V1 文档中心

欢迎来到 File Server V1 的文档中心。无论您是想快速使用API，还是希望深入了解其架构并参与开发，这里都能为您提供指引。

## 核心文档

我们建议您根据自己的需求，从以下文档开始：

| 文档                                | 描述                                                               | 主要读者                   |
| ----------------------------------- | ------------------------------------------------------------------ | -------------------------- |
| 🚀 **[快速开始 (QUICK_START.md)]**   | 5分钟上手指南，教您如何快速部署和测试API。                         | 新用户、开发者             |
| 📄 **[API 参考 (API_REFERENCE.md)]** | 详细的 RESTful API 接口文档，包含所有端点、请求和响应示例。        | 前端/后端开发者、API使用者 |
| 🏗️ **[架构设计 (ARCHITECTURE.md)]**  | 深入解析系统核心设计理念、数据处理流水线、模块化组件和数据库设计。 | 核心开发者、架构师         |
| 🛠️ **[开发指南 (DEVELOPMENT.md)]**   | V1 版本的开发环境搭建、代码规范、测试和部署指南。                  | 贡献者、后端开发者         |
| 🤝 **[贡献指南 (CONTRIBUTING.md)]**  | 如何为项目贡献代码、报告问题或提出建议。                           | 开源贡献者                 |

[快速开始 (QUICK_START.md)]: QUICK_START.md
[API 参考 (API_REFERENCE.md)]: API_REFERENCE.md
[架构设计 (ARCHITECTURE.md)]: ARCHITECTURE.md
[开发指南 (DEVELOPMENT.md)]: DEVELOPMENT.md
[贡献指南 (CONTRIBUTING.md)]: CONTRIBUTING.md

## 项目概述

File Server 是一个专为企业级应用设计的、支持高并发的智能文件处理服务。它提供从文件存储、内容提取、到知识库索引的全链路功能。

### 核心特性

- **三层API设计**: 清晰的文件、处理、知识库分层。
- **Markdown核心**: 所有文档被处理为标准的Markdown，实现内容与表现分离。
- **异步处理流水线**: 高性能、可扩展的文档处理能力。
- **企业级存储**: 基于 MinIO 和 PostgreSQL (pgvector) 构建，稳定可靠。

我们希望这份文档能帮助您更好地理解和使用 UniFile。如果您发现任何问题，欢迎通过 [Issues](https://github.com/your-repo/issues) 提出。
