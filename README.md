# Unifiles

简洁、可扩展的文件处理与知识库服务平台。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 特性

- **📁 文件管理**: 支持多种文件格式上传（PDF, Word, PPT, 图片等）
- **🔍 内容提取**: OCR 文本提取、格式转换、Markdown 标准化
- **📚 知识库**: 向量化语义检索、灵活的分块策略
- **⚡ 高性能**: 异步 I/O、连接池管理、Redis 缓存
- **🔒 安全**: API Key 认证、数据加密、多租户隔离
- **📊 可观测**: OpenTelemetry 追踪、结构化日志

## 📖 文档

- **[在线文档](https://unifiles.dev/docs)** - 完整的用户文档
- **[快速开始](https://unifiles.dev/docs/quickstart)** - 5分钟上手
- **[API 参考](https://unifiles.dev/docs/api-reference)** - API 调用文档

## 🏗️ 架构设计

如果你想深入了解 Unifiles 的内部实现：

- **[架构设计文档](ARCHITECTURE.md)** - 系统架构、三层设计、数据库Schema
- **[贡献指南](CONTRIBUTING.md)** - 如何参与开发

## 🛠️ 快速开始

### 前置要求

- Python 3.11+
- PostgreSQL 15+ (with pgvector)
- Redis 7+
- MinIO (或兼容 S3 的对象存储)

### 安装

```bash
# 克隆仓库
git clone https://github.com/ppppangu/Unifiles.git
cd Unifiles

# 安装依赖（推荐使用 uv）
uv sync

# 或使用 pip
pip install -e .
```

### 配置

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
vim .env
```

### 启动服务

```bash
# 启动 API 服务器
uv run uvicorn unifiles.server.main:app --host 0.0.0.0 --port 8088 --reload

# 启动 Worker（另一个终端）
uv run python -m unifiles.workers.upload_worker
uv run python -m unifiles.workers.extraction_worker
```

### 使用 Docker

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 🧪 开发

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/integration/

# 查看覆盖率
uv run pytest --cov=unifiles
```

### 代码质量

```bash
# 格式化代码
uv run python scripts/dev/format.py

# 代码检查
uv run python scripts/check/lint.py

# 类型检查
uv run python scripts/check/type_check.py

# 运行所有检查
uv run python scripts/check/validate_all.py
```

### 清理

```bash
# 预览清理内容
python scripts/dev/clean.py

# 执行清理
python scripts/dev/clean.py --apply

# 包含 .venv 等重项
python scripts/dev/clean.py --apply --all
```

## 📂 项目结构

```
unifiles/                  # 主包（发布到 PyPI）
├── unifiles/              # 核心代码
│   ├── server/           # SaaS 服务端（FastAPI 应用层）
│   ├── client/           # Python 客户端库
│   ├── core/             # 共享核心业务逻辑
│   ├── workers/          # 后台任务处理
│   ├── types/            # 类型定义（聚合层）
│   └── config/           # 配置管理
├── tests/                # 测试套件
├── scripts/              # 开发与运维脚本
├── docs/                 # 用户文档（MkDocs）
├── examples/             # 使用示例
├── ARCHITECTURE.md       # 架构设计文档
├── CONTRIBUTING.md       # 贡献指南
└── README.md             # 本文件
```

**使用场景**:
- **SaaS 服务**: 从 `unifiles.server` 导入
- **客户端库**: 从 `unifiles.client` 导入
- **自部署**: 从 `unifiles.server` + `unifiles.core` 导入
- **直接 API 调用**: 从 `unifiles.core.services` 导入

## 🤝 贡献

我们欢迎各种形式的贡献！查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

### 贡献者

感谢所有为 Unifiles 做出贡献的开发者！

## 📄 许可证

本项目采用 [Apache License 2.0](LICENSE)。

## 🔗 链接

- **文档**: https://unifiles.dev/docs
- **GitHub**: https://github.com/ppppangu/Unifiles
- **Issues**: https://github.com/ppppangu/Unifiles/issues

## 💬 支持

如果遇到问题或有建议：

1. 查看[在线文档](https://unifiles.dev/docs)
2. 搜索[已有 Issues](https://github.com/ppppangu/Unifiles/issues)
3. 提交新的 Issue

---

<div align="center">
  Made with ❤️ by the Unifiles Team
</div>
