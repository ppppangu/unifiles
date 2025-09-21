# 🚀 快速开始指南

本指南将帮助您在5分钟内快速部署和运行 Unifiles V1 API。

## 📋 概述

**🔥 V1 RESTful API** (推荐) - 现代化、安全、分层的API，运行在端口 `8088`。

---

## 🎯 5分钟快速部署

### 1. 环境准备

- Git
- Python 3.8+ (推荐使用 `uv` 进行包管理)
- Docker 和 Docker Compose

```bash
# 克隆项目
git clone <repository-url>
cd Unifiles

# 安装依赖（推荐使用uv）
uv sync --dev

# 或者使用 pip
# python -m venv .venv
# source .venv/bin/activate
# pip install -e ".[dev]"
```

### 2. 启动基础服务 (Docker)

项目依赖 PostgreSQL (with pgvector) 和 MinIO。使用 Docker Compose 可以一键启动：

```bash
# 启动数据库和对象存储服务
docker-compose -f docker-compose.dev.yml up -d
```
*这会根据 `docker-compose.dev.yml` 文件启动 `postgres` 和 `minio` 容器。*

- **MinIO 控制台**: http://localhost:9001 (默认用户/密码: `minioadmin`/`minioadmin`)
- **PostgreSQL 端口**: `5432`

### 3. 配置文件

创建 `config/config.yaml` 文件，内容如下：

```yaml
api:
  title: "Unifiles API"
  version: "1.1.0"

server_components:
  minio:
    host: "localhost"
    port: 9000
    access_key: "minioadmin"
    secret_key: "minioadmin"
    bucket_name: "unifiles"
    use_public_url: true # 设置为true以获取可访问的URL
    public_url_prefix: "http://localhost:9000"

  pg_vector:
    host: "localhost"
    port: 5432
    database: "unifiles"
    user: "postgres"
    password: "password"

# (可选) 其他服务配置
# convert_format_server:
#   - url: "http://localhost:8090"
# mineru_server:
#   - url: "http://localhost:8091"
```

### 4. 启动 V1 API 服务

```bash
# 运行 V1 API 服务 (开发模式，带自动重载)
uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
```
服务启动后，API 文档位于 http://localhost:8088/docs。

### 5. 初始化数据库

首次启动时，需要初始化数据库表和策略。

```bash
# 执行数据库初始化脚本
python scripts/init_db.py
```

### 6. 创建API访问密钥

为了调用需要认证的接口，您需要创建一个访问密钥。

```sql
-- 1. 连接到数据库
psql -h localhost -U postgres -d unifiles

-- 2. 创建一个测试用户
INSERT INTO unifiles.users (id) VALUES ('test_user');

-- 3. 为用户创建访问密钥
INSERT INTO unifiles.access_keys (user_id, name)
VALUES ('test_user', 'Development API Key');

-- 4. 查看生成的密钥（此密钥仅显示一次，请妥善保管）
SELECT access_key FROM unifiles.access_keys
WHERE user_id = 'test_user' ORDER BY created_at DESC LIMIT 1;
```

---

## 🧪 V1 API 核心流程测试

以下脚本展示了从上传文件、提取内容到索引知识库的完整流程。

```bash
# --- 请将下面的变量替换为您的实际值 ---
export API_URL="http://localhost:8088"
# 从上一步获取的API密钥
export TOKEN="[REDACTED]"
# 要创建的知识库ID
export KB_ID="my_test_kb"
# 用于测试的文件路径
export TEST_FILE_PATH="./README.md"
# -----------------------------------------

echo "### 1. 上传文件..."
UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TEST_FILE_PATH")

FILE_ID=$(echo $UPLOAD_RESPONSE | jq -r '.file.file_id')
if [ -z "$FILE_ID" ] || [ "$FILE_ID" == "null" ]; then
  echo "文件上传失败!"
  echo $UPLOAD_RESPONSE
  exit 1
fi
echo "文件上传成功, File ID: $FILE_ID"
echo ""

echo "### 2. 提取文件内容..."
EXTRACT_RESPONSE=$(curl -s -X POST "$API_URL/files/$FILE_ID/extract" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}')

EXTRACTION_ID=$(echo $EXTRACT_RESPONSE | jq -r '.extracted_content.extraction_id')
if [ -z "$EXTRACTION_ID" ] || [ "$EXTRACTION_ID" == "null" ]; then
  echo "内容提取失败!"
  echo $EXTRACT_RESPONSE
  exit 1
fi
echo "内容提取成功, Extraction ID: $EXTRACTION_ID"
echo ""

echo "### 3. 索引到知识库..."
INDEX_RESPONSE=$(curl -s -X POST "$API_URL/knowledge-bases/$KB_ID/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"extraction_id\": \"$EXTRACTION_ID\", \"knowledge_base_id\": \"$KB_ID\", \"chunk_strategy\": \"semantic\"}")

DOCUMENT_ID=$(echo $INDEX_RESPONSE | jq -r '.document.document_id')
if [ -z "$DOCUMENT_ID" ] || [ "$DOCUMENT_ID" == "null" ]; then
  echo "索引失败!"
  echo $INDEX_RESPONSE
  exit 1
fi
echo "索引任务已启动, Document ID: $DOCUMENT_ID"
echo ""

echo "✅ 核心流程测试完成！"
```

---

## 🐳 Docker Compose 部署 (V1)

如果您希望将 V1 API 作为容器运行，可以使用以下 `docker-compose.yml` 配置。

```yaml
version: '3.8'

services:
  # V1 RESTful API
  unifiles-v1:
    build:
      context: .
      dockerfile: Dockerfile # 假设项目有生产用的Dockerfile
    ports:
      - "8088:8088"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/unifiles
      - MINIO_ENDPOINT=minio:9000
      # 其他所需的环境变量
    depends_on:
      - postgres
      - minio
    volumes:
      - ./config:/app/config

  # 数据库
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: unifiles
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # 对象存储
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

---

## 🔍 故障排除

- **数据库连接失败**: 确保 `postgres` 容器正在运行 (`docker ps`)，并且 `config.yaml` 中的连接信息正确。
- **MinIO连接问题**: 确保 `minio` 容器正在运行，并且 `config.yaml` 中的 `access_key` 和 `secret_key` 正确。
- **认证失败**: 确认请求头中的 `Bearer Token` 正确无误，且未过期。
- **端口冲突**: 如果 `8088` 或其他端口被占用，请在 `uvicorn` 命令或 `docker-compose.yml` 中修改为其他可用端口。

---

## 📚 下一步

- **熟悉API**: 查看 [API参考文档 (API_REFERENCE.md)](API_REFERENCE.md)
- **理解架构**: 阅读 [架构设计文档 (ARCHITECTURE.md)](ARCHITECTURE.md)
- **深入开发**: 参考 [开发文档 (DEVELOPMENT.md)](DEVELOPMENT.md)