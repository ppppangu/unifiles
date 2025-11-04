# Unifiles Documentation

欢迎来到 Unifiles 文档！Unifiles 是一个简洁、可扩展的文件处理与知识库服务平台。

## 根据您的角色快速开始

### 🎯 我是最终用户
- [快速开始](getting-started/index.md) - 5分钟上手 Unifiles
- [功能介绍](features/index.md) - 了解 Unifiles 能做什么
- [API 参考](api/reference.md) - 查看 API 文档

### 👨‍💻 我是开发者
- [开发环境搭建](development/index.md) - 开始贡献代码
- [架构设计](architecture/index.md) - 理解系统架构
- [贡献指南](development/contributing.md) - 如何参与项目

### 🚀 我是运维人员
- [部署指南](deployment/deployment.md) - 部署到生产环境
- [可观测性](observability/index.md) - 配置监控和日志
- [CI/CD 设置](deployment/cicd.md) - 自动化部署流程

### 🏗️ 我是架构师
- [三层架构设计](architecture/three-layer-design.md) - 核心架构模式
- [深度技术分析](architecture/deep-analysis.md) - 技术决策和权衡
- [数据流设计](architecture/data-flow.md) - 数据处理流程

## 核心特性

### 📁 文件管理（第一层）
- 多格式文件上传（PDF, Word, PPT, 图片等）
- MinIO 对象存储集成
- 文件元数据管理
- 访问控制与权限管理

### 🔍 内容提取（第二层）
- OCR 文本提取
- 文档格式转换
- 内容结构化处理
- 以 Markdown 为核心的内容存储

### 📚 知识库管理（第三层）
- 向量化与语义检索
- 灵活的分块策略
- 多知识库隔离
- 高效的相似度搜索

## 技术栈

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL + pgvector
- **Storage**: MinIO
- **Cache**: Redis
- **Observability**: OpenTelemetry
- **Package Manager**: uv

## 快速链接

- [GitHub 仓库](https://github.com/ppppangu/Unifiles)
- [问题反馈](https://github.com/ppppangu/Unifiles/issues)
- [发布日志](releases/release-notes.md)
- [开发进度](development/progress.md)

## 许可证

MIT License
