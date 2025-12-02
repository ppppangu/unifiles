<p align="center">
  <img src="docs/assets/logo.svg" alt="Unifiles" width="120" />
</p>

<h1 align="center">Unifiles</h1>

<p align="center">
  <strong>LLM 应用层的文档处理基础设施</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/ppppangu/Unifiles/actions"><img src="https://github.com/ppppangu/Unifiles/workflows/CI/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="https://unifiles.dev">文档</a> •
  <a href="https://unifiles.dev/quickstart">快速开始</a> •
  <a href="https://unifiles.dev/api-reference">API 参考</a> •
  <a href="https://unifiles.dev/self-hosting">自部署</a>
</p>

---

Unifiles 是一个自托管的文档处理平台，为 AI 应用提供**文件存储**、**内容提取**和**知识库管理**的完整解决方案。

## 核心特性

- **三层解耦架构** - 文件存储、内容提取、知识库完全独立，灵活组合
- **Markdown 即真相** - 统一的 Markdown 输出，消除格式碎片化
- **命名空间化 SDK** - 类 Stripe 的 API 设计，简洁直观
- **完全自托管** - 数据完全由你控制，支持 Docker/Kubernetes

## 快速体验

```bash
pip install unifiles
```

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 上传文件
file = client.files.upload("document.pdf")

# 提取内容为 Markdown
extraction = client.extractions.create(file_id=file.id)
extraction.wait()
print(extraction.markdown)

# 创建知识库并搜索
kb = client.knowledge_bases.create(name="my-docs")
client.knowledge_bases.documents.create(kb_id=kb.id, file_id=file.id)

results = client.knowledge_bases.search(kb_id=kb.id, query="关键内容")
```

## 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 知识库   │  语义搜索、向量索引、RAG 就绪          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 内容提取 │  OCR、格式转换、Markdown 标准化        │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 文件存储 │  上传、元数据、去重、访问控制          │
└─────────────────────────────────────────────────────────────┘
```

每一层独立运作，你可以：
- 只用 Layer 1 做文件存储
- 用 Layer 1 + 2 做文档提取
- 用完整三层构建 RAG 应用

## 自部署

### Docker Compose (推荐)

```bash
git clone https://github.com/ppppangu/Unifiles.git
cd Unifiles

cp .env.example .env
# 编辑 .env 配置

docker-compose up -d
```

### 从源码运行

```bash
# 安装依赖
uv sync

# 启动 API 服务
uv run uvicorn unifiles.server.main:app --port 8088 --reload

# 启动后台 Worker
uv run python -m unifiles.workers.upload_worker
uv run python -m unifiles.workers.extraction_worker
```

详细部署指南请参考 [自部署文档](https://unifiles.dev/self-hosting)。

## 技术栈

| 组件 | 技术 |
|------|------|
| API 框架 | FastAPI |
| 数据库 | PostgreSQL + pgvector |
| 缓存/队列 | Redis |
| 对象存储 | MinIO / S3 |
| 嵌入模型 | OpenAI / 自定义 |

## 文档

| 文档 | 说明 |
|------|------|
| [快速开始](https://unifiles.dev/quickstart) | 5 分钟上手 |
| [了解 Unifiles](https://unifiles.dev/what-is-unifiles) | 核心概念和设计理念 |
| [使用 API](https://unifiles.dev/using-the-api) | API 使用指南 |
| [Cookbook](https://unifiles.dev/cookbook) | 渐进式教程和代码示例 |
| [API 参考](https://unifiles.dev/api-reference) | 完整 API 文档 |
| [技术深潜](https://unifiles.dev/under-the-hood) | 架构和内部实现 |
| [自部署](https://unifiles.dev/self-hosting) | 部署和运维指南 |

## 项目结构

```
unifiles/
├── unifiles/
│   ├── server/       # FastAPI 应用层
│   ├── client/       # Python 客户端库
│   ├── core/         # 核心业务逻辑
│   └── workers/      # 后台任务处理
├── docs/             # 文档源文件
├── tests/            # 测试套件
├── scripts/          # 开发脚本
└── examples/         # 使用示例
```

## 开发

```bash
# 运行测试
uv run pytest

# 代码格式化
uv run python scripts/dev/format.py

# 代码检查
uv run python scripts/check/validate_all.py

# 构建文档
uv run mkdocs serve
```

## 贡献

我们欢迎各种形式的贡献！请查看 [贡献指南](docs/CONTRIBUTING.md)。

## 许可证

[Apache License 2.0](LICENSE)

## 链接

- [文档](https://unifiles.dev)
- [GitHub](https://github.com/ppppangu/Unifiles)
- [Issues](https://github.com/ppppangu/Unifiles/issues)
- [Discussions](https://github.com/ppppangu/Unifiles/discussions)
