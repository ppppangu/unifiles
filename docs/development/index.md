# 🛠️ V1 开发文档

本篇文档为 Unifiles V1 的核心开发者提供深入的开发指导、架构说明和实践指南。

## 🚀 开发环境搭建

### 环境要求

- Python 3.8+
- Docker & Docker Compose
- `uv` (推荐) 或 `pip`

### 快速搭建

```bash
# 1. 克隆并进入项目
git clone <repository-url>
cd Unifiles

# 2. 安装依赖
uv sync --dev

# 3. 启动依赖服务 (PostgreSQL + MinIO)
docker-compose -f docker-compose.dev.yml up -d

# 4. 初始化数据库
# 首次启动需要初始化数据库表结构
python scripts/init_db.py

# 5. 启动 V1 API 服务
# 服务将运行在 http://localhost:8088
uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
```

---

## 🏗️ 项目架构

关于系统架构、数据处理流水线、数据模型和数据库设计的详细信息，请参阅 **[架构设计文档 (ARCHITECTURE.md)](architecture/three-layer-design.md)**。

### 目录结构 (V1 核心)

```
Unifiles/
├── 📁 server/                 # 服务器端代码
│   ├── 📁 core/              # 🎯 核心模块 (可复用)
│   │   ├── database/         # 数据库抽象
│   │   ├── pipelines/        # 处理流水线
│   │   ├── services/         # 业务服务
│   │   └── utils/            # 工具函数
│   └── 📁 app/
│       └── 📁 v1/             # 🚀 V1 RESTful API
│           ├── routers/      # API路由
│           ├── schemas.py    # API数据模型
│           └── main.py       # 应用入口
├── 📁 docs/                 # 📚 项目文档
├── 📁 examples/             # 🧪 使用示例
├── 📁 tests/                # 单元与集成测试
└── 📁 scripts/              # 🔧 工具脚本 (如 db 初始化)
```

---

## 🧩 核心模块简介

`server/core/` 目录包含了项目可复用的核心业务逻辑，其设计遵循高内聚、低耦合的原则。

- **`pipelines`**: 定义了文档处理的流水线模式，包括文件转换、OCR、分块、向量化等阶段。
- **`processors`**: 各个处理阶段的具体实现。
- **`strategies`**: 实现了可插拔的策略，如不同的分块算法和嵌入模型。
- **`database`**: 负责与 PostgreSQL 数据库交互，包括元数据和向量数据的管理。
- **`storage`**: 负责与 MinIO 对象存储交互。

更详细的设计思想请参考 **[架构设计文档 (ARCHITECTURE.md)](architecture/three-layer-design.md)**。

---

## 🧪 开发与测试指南

### 添加新的API端点

在 `server/app/v1/routers/` 目录下创建或修改路由文件，并使用 FastAPI 的装饰器定义端点。

```python
# server/app/v1/routers/files.py

@router.post("/{file_id}/analyze", response_model=AnalysisResponse)
async def analyze_file(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    analysis_type: str = Query("basic", description="分析类型")
):
    """分析文件内容"""
    user_id = request.state.user_id
    # 1. 从数据库获取文件信息
    # 2. 调用核心服务进行分析
    # 3. 返回标准化的响应
    pass
```

### 测试指南

项目使用 `pytest` 进行测试。测试代码位于 `tests/` 目录下。

#### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定文件的测试
pytest tests/test_api.py

# 查看测试覆盖率
pytest --cov=server --cov-report=html
```

#### 集成测试示例 (V1 流程)

```python
# tests/integration/test_v1_workflow.py
import pytest
from fastapi.testclient import TestClient
from server.app.v1.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_full_workflow(auth_headers: dict):
    """测试上传-提取-索引的完整流程"""
    # 1. 上传文件
    with open("tests/fixtures/sample.pdf", "rb") as f:
        upload_response = client.post("/files", headers=auth_headers, files={"file": f})
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file"]["file_id"]

    # 2. 提取内容
    extract_response = client.post(f"/files/{file_id}/extract", headers=auth_headers, json={"mode": "normal"})
    assert extract_response.status_code == 200
    extraction_id = extract_response.json()["extracted_content"]["extraction_id"]

    # 3. 索引到知识库
    index_response = client.post(
        f"/knowledge-bases/test_kb/documents",
        headers=auth_headers,
        json={
            "extraction_id": extraction_id,
            "knowledge_base_id": "test_kb",
            "chunk_strategy": "semantic"
        }
    )
    assert index_response.status_code == 200
    assert "document_id" in index_response.json()["document"]
```

---

## 🚀 部署指南

### 开发环境 (Docker Compose)

`docker-compose.yml` 文件已为您配置好了 V1 API 的开发环境。

```yaml
# docker-compose.yml (部分)
services:
  unifiles-v1:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports: ["8088:8088"]
    volumes: [".:/app"]
    environment:
      - PYTHONPATH=/app
    command: uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
```

### 生产环境 (Dockerfile)

项目根目录下的 `Dockerfile` 可用于构建生产镜像。

```dockerfile
# Dockerfile (生产环境示例)
FROM python:3.11-slim
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 健康检查
HEALTHCHECK CMD curl -f http://localhost:8088/health || exit 1

# 启动命令
CMD ["uvicorn", "server.app.v1.main:app", "--host", "0.0.0.0", "--port", "8088"]
```

---

## 🤝 贡献指南

我们欢迎任何形式的贡献！在您提交代码之前，请确保：

1.  代码遵循项目规范和风格。
2.  为新功能添加了必要的单元测试和集成测试。
3.  更新了相关的文档。
4.  所有测试均已通过。

更详细的贡献流程、代码规范和提交信息格式，请参阅 **[贡献指南 (CONTRIBUTING.md)](contributing.md)**。

---

## 🔍 调试指南

- **日志**: V1 服务的日志位于 `server/app/v1/logs/` 目录下。在开发模式下，日志会实时输出到控制台。
- **断点调试**: 在代码中加入 `import pdb; pdb.set_trace()` 或 `import ipdb; ipdb.set_trace()` 可以在运行时进入交互式调试器。
- **远程调试**: 使用 `debugpy` 等工具可以连接到正在运行的进程进行远程调试。
