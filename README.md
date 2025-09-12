# 📁 Unifiles

> 企业级文档处理系统 - 支持文件存储、OCR处理、向量化和知识图谱生成

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org) [![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-blue.svg)](https://postgresql.org) [![MinIO](https://img.shields.io/badge/MinIO-Latest-orange.svg)](https://min.io)

## ⚡ 快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 启动服务
uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload

# 3. 访问文档
open http://localhost:8088/docs
```

## 🎯 核心特性

- **🔒 企业级安全** - Bearer Token认证 + 数据库行级安全
- **🏗️ RESTful API** - 标准化REST接口设计
- **🧩 模块化架构** - 可插拔组件，易于扩展
- **📄 多格式支持** - 28+种文件格式，智能OCR处理
- **🧠 向量化存储** - PostgreSQL + pgvector语义检索
- **🔄 向后兼容** - Legacy和V1双模式运行

## 🏗️ 架构概览

```
Unifiles/
├── server/
│   ├── core/           # 🎯 核心模块（可复用）
│   │   ├── database/   # 数据库抽象层
│   │   ├── pipelines/  # 处理管道层
│   │   ├── services/   # 业务服务层
│   │   └── utils/      # 工具函数层
│   └── app/            # 🚀 应用层
│       ├── legacy/     # Legacy API (端口8087)
│       └── v1/         # RESTful API (端口8088)
├── docs/               # 📚 文档
├── examples/           # 🧪 示例
└── 数据库建表逻辑/      # 🗄️ 数据库架构
```

## 📋 API概览

### V1 RESTful API (推荐)

```bash
# 认证
Authorization: Bearer [REDACTED]

# 文件管理
GET    /files/types              # 获取支持文件类型
POST   /files                    # 上传文件
GET    /files/{file_id}          # 获取文件信息
DELETE /files/{file_id}          # 删除文件

# 知识库
POST   /knowledge-bases/{id}/documents  # 处理文档
GET    /knowledge-bases/{id}/documents  # 获取文档列表
DELETE /knowledge-bases/{id}/documents/{doc_id}  # 删除文档

# 系统
GET    /health                   # 健康检查
GET    /docs                     # API文档
```

### 使用示例

```python
import httpx

# 上传文件
async with httpx.AsyncClient() as client:
    with open("document.pdf", "rb") as f:
        response = await client.post(
            "http://localhost:8088/files",
            headers={"Authorization": "Bearer sk_your_key"},
            files={"file": f}
        )
    file_info = response.json()["file"]
    
    # 处理到知识库
    response = await client.post(
        f"http://localhost:8088/knowledge-bases/my_kb/documents",
        headers={"Authorization": "Bearer sk_your_key"},
        json={"file_id": file_info["file_id"], "mode": "simple"}
    )
```

## 🛠️ 部署

### 开发环境

```bash
# 启动基础服务
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_DB=Unifiles -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password pgvector/pgvector:pg16

# 初始化数据库
psql -h localhost -U postgres -d Unifiles -f 数据库建表逻辑/021-create-document-table.sql
```

### 生产环境

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports: ["8088:8088"]
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/Unifiles
    depends_on: [postgres, minio]
    
  postgres:
    image: pgvector/pgvector:pg16
    environment: {POSTGRES_DB: Unifiles, POSTGRES_USER: postgres, POSTGRES_PASSWORD: password}
    
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment: {MINIO_ROOT_USER: minioadmin, MINIO_ROOT_PASSWORD: minioadmin}
```

## 📚 文档

- **[快速开始](docs/QUICK_START.md)** - 5分钟部署指南
- **[开发指南](docs/DEVELOPMENT.md)** - 架构说明和开发指南
- **[贡献指南](docs/CONTRIBUTING.md)** - 如何参与项目开发

## 🤝 技术栈

| 组件         | 技术                  | 用途                  |
| ------------ | --------------------- | --------------------- |
| **Web框架**  | FastAPI               | API服务               |
| **数据库**   | PostgreSQL + pgvector | 结构化数据 + 向量存储 |
| **对象存储** | MinIO                 | 文件存储              |
| **认证**     | Bearer Token + RLS    | 安全认证              |
| **OCR**      | 可插拔架构            | 文档识别              |

## 📊 系统要求

- **Python**: 3.8+
- **数据库**: PostgreSQL 12+ (with pgvector)
- **存储**: MinIO 或 S3 兼容存储
- **内存**: 建议 2GB+
- **存储**: 建议 10GB+ 可用空间

## 🎯 路线图

- [x] ✅ RESTful API设计
- [x] ✅ Bearer Token认证
- [x] ✅ 模块化架构重构
- [x] ✅ 数据库行级安全
- [ ] 🔄 Web控制台界面
- [ ] 🔄 分布式处理队列
- [ ] 🔄 Kubernetes部署支持

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

感谢所有贡献者和开源社区的支持！

--- 

**⭐ 觉得有用？给个Star支持一下！**
