# 🚀 快速开始指南

## 📋 概述

File Server提供两种API模式：

- **🔥 V1 RESTful API** (推荐) - 现代化、安全的API，端口8088
- **🔄 Legacy API** (兼容) - 向后兼容模式，端口8087

两种模式可以同时运行，便于平滑迁移。

---

## 🎯 5分钟快速部署

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd file_server

# 安装依赖（推荐使用uv）
uv sync

# 或使用pip
pip install -e .
```

### 2. 基础服务配置

#### 2.1 启动MinIO对象存储
```bash
# Docker方式（推荐）
docker run -d \
  --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# 访问控制台: http://localhost:9001
# 用户名/密码: minioadmin/minioadmin
```

#### 2.2 启动PostgreSQL数据库
```bash
# Docker方式
docker run -d \
  --name postgres \
  -p 5432:5432 \
  -e POSTGRES_DB=file_server \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  pgvector/pgvector:pg16

# 等待启动后执行数据库初始化
psql -h localhost -U postgres -d file_server -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. 配置文件设置

```bash
# 创建配置目录
mkdir -p config

# 创建基础配置文件
cat > config/config.yaml << 'EOF'
api:
  title: "File Server API"
  version: "1.0.0"

server_components:
  minio:
    host: "localhost"
    port: 9000
    access_key: "minioadmin"
    secret_key: "minioadmin" 
    bucket_name: "file-server"
    use_public_url: false
    
  pg_vector:
    host: "localhost"
    port: 5432
    database: "file_server"
    user: "postgres"
    password: "password"

convert_format_server:
  - url: "http://localhost:8090"  # 可选：格式转换服务

mineru_server:
  - url: "http://localhost:8091"  # 可选：OCR服务
EOF
```

### 4. 环境变量配置
```bash
# 创建.env文件（可选，用于OCR等功能）
cat > .env << 'EOF'
# OCR服务配置（可选）
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_OCR_MODEL=mistral-ocr-latest

# 其他可选配置
LOG_LEVEL=INFO
EOF
```

---

## 🔥 方式一：V1 RESTful API（推荐）

### 启动V1服务

```bash
# 开发模式（自动重载）
cd server/app/v1
uv run uvicorn main:app --host 0.0.0.0 --port 8088 --reload

# 或直接运行
python -m uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
```

### 初始化数据库表

```bash
# 执行数据库建表脚本
psql -h localhost -U postgres -d file_server -f 数据库建表逻辑/021-create-document-table.sql
psql -h localhost -U postgres -d file_server -f 数据库建表逻辑/041-create-file-table.sql
psql -h localhost -U postgres -d file_server -f 数据库建表逻辑/052-create-access-key-table.sql
psql -h localhost -U postgres -d file_server -f 数据库建表逻辑/051-create-rls-policies.sql
```

### 创建API访问密钥

```sql
-- 连接数据库
psql -h localhost -U postgres -d file_server

-- 创建用户
INSERT INTO chunk_schema.users (id) VALUES ('test_user');

-- 创建access key
INSERT INTO chunk_schema.access_keys (user_id, name) 
VALUES ('test_user', 'Development API Key');

-- 查看生成的密钥（仅显示一次）
SELECT access_key FROM chunk_schema.access_keys 
WHERE user_id = 'test_user' ORDER BY created_at DESC LIMIT 1;
```

### 测试V1 API

```bash
# 健康检查
curl http://localhost:8088/health

# 获取支持的文件类型
curl http://localhost:8088/files/types

# 上传文件（需要替换为实际的access_key）
curl -X POST "http://localhost:8088/files" \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@test.pdf"

# 查看API文档
# 浏览器打开: http://localhost:8088/docs
```

---

## 🔄 方式二：Legacy API（兼容模式）

### 启动Legacy服务

```bash
# 方式1: 使用启动脚本
cd server/app/legacy
python start_legacy_server.py

# 方式2: 直接启动
uv run uvicorn server.app.legacy.main:app --host 0.0.0.0 --port 8087 --reload
```

### 测试Legacy API

```bash
# 健康检查
curl http://localhost:8087/health

# 上传文件
curl -X POST "http://localhost:8087/upload_minio" \
  -F "upload_file=@test.pdf" \
  -F "user_id=test_user"

# 处理文档
curl -X POST "http://localhost:8087/process" \
  -d "user_id=test_user&file_url=http://your-file-url&mode=simple"
```

---

## 🧪 完整测试流程

### V1 RESTful API完整流程

```bash
# 1. 设置变量
export API_URL="http://localhost:8088"
export TOKEN="[REDACTED]"

# 2. 上传文件
UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf")

echo "上传响应: $UPLOAD_RESPONSE"

# 3. 提取file_id
FILE_ID=$(echo $UPLOAD_RESPONSE | jq -r '.file.file_id')
echo "文件ID: $FILE_ID"

# 4. 获取文件信息
curl -s -X GET "$API_URL/files/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .

# 5. 处理文档到知识库
PROCESS_RESPONSE=$(curl -s -X POST "$API_URL/knowledge-bases/kb_test/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"mode\": \"simple\"}")

echo "处理响应: $PROCESS_RESPONSE"

# 6. 提取文档ID
DOC_ID=$(echo $PROCESS_RESPONSE | jq -r '.document.document_id')
echo "文档ID: $DOC_ID"
```

### Legacy API完整流程

```bash
# 1. 设置变量
export LEGACY_URL="http://localhost:8087" 
export USER_ID="test_user"

# 2. 上传文件
UPLOAD_RESPONSE=$(curl -s -X POST "$LEGACY_URL/upload_minio" \
  -F "upload_file=@test.pdf" \
  -F "user_id=$USER_ID")

echo "上传响应: $UPLOAD_RESPONSE"

# 3. 提取文件URL
FILE_URL=$(echo $UPLOAD_RESPONSE | jq -r '.data.public_url')
echo "文件URL: $FILE_URL"

# 4. 处理文档
PROCESS_RESPONSE=$(curl -s -X POST "$LEGACY_URL/process" \
  -d "user_id=$USER_ID&file_url=$FILE_URL&mode=simple")

echo "处理响应: $PROCESS_RESPONSE"
```

---

## 🐳 Docker Compose部署

### 创建docker-compose.yml

```yaml
version: '3.8'

services:
  # V1 RESTful API
  file-server-v1:
    build: 
      context: .
      dockerfile: Dockerfile
    ports:
      - "8088:8088"
    environment:
      - API_MODE=v1
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/file_server
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - postgres
      - minio
    volumes:
      - ./config:/app/config
      
  # Legacy API
  file-server-legacy:
    build:
      context: .
      dockerfile: Dockerfile  
    ports:
      - "8087:8087"
    environment:
      - API_MODE=legacy
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/file_server
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - postgres
      - minio
    volumes:
      - ./config:/app/config

  # 数据库
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: file_server
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

### 使用Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f file-server-v1

# 停止服务
docker-compose down
```

---

## 🔍 故障排除

### 常见问题

#### 1. 数据库连接失败
```bash
# 检查PostgreSQL是否启动
docker ps | grep postgres

# 测试数据库连接
psql -h localhost -U postgres -d file_server -c "SELECT version();"

# 检查pgvector扩展
psql -h localhost -U postgres -d file_server -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

#### 2. MinIO连接问题
```bash
# 检查MinIO服务
curl http://localhost:9000/minio/health/live

# 检查MinIO控制台
# 浏览器访问: http://localhost:9001
```

#### 3. 认证问题（V1 API）
```bash
# 检查access_key是否存在且有效
psql -h localhost -U postgres -d file_server -c "
SELECT id, user_id, name, is_active, expires_at 
FROM chunk_schema.access_keys 
WHERE access_key = '[REDACTED]';"

# 验证token
curl -X GET "http://localhost:8088/files/types" \
  -H "Authorization: Bearer [REDACTED]"
```

#### 4. 文件上传失败
```bash
# 检查文件大小（限制100MB）
ls -lh test.pdf

# 检查文件类型是否支持
curl http://localhost:8088/files/types

# 检查MinIO桶是否存在
docker exec -it minio mc ls local/
```

#### 5. 端口冲突
```bash
# 检查端口占用
netstat -tlnp | grep :8088
netstat -tlnp | grep :8087

# 使用其他端口
uvicorn server.app.v1.main:app --port 8089
```

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG

# V1 API调试模式
uvicorn server.app.v1.main:app --log-level debug --reload

# Legacy API调试模式  
uvicorn server.app.legacy.main:app --log-level debug --reload

# 查看应用日志
tail -f server/app/v1/logs/$(date +%Y-%m-%d).log
tail -f server/app/legacy/logs/$(date +%Y-%m-%d).log
```

---

## 📚 下一步

### 开发学习路径

1. **熟悉API** → 查看 [API参考文档](API_REFERENCE.md)
2. **理解架构** → 阅读 [架构设计文档](ARCHITECTURE.md)  
3. **深入开发** → 参考 [开发文档](DEVELOPMENT.md)
4. **查看示例** → 运行 `examples/` 目录下的示例代码

### 生产部署考虑

1. **安全配置** → 更换默认密码，启用HTTPS
2. **性能优化** → 配置连接池、缓存
3. **监控告警** → 集成日志和监控系统
4. **备份策略** → 数据库和文件备份方案

### 开发工具推荐

```bash
# API测试工具
curl, httpie, Postman

# 数据库管理
pgAdmin, DBeaver

# 对象存储管理  
MinIO Console (http://localhost:9001)

# API文档
Swagger UI (http://localhost:8088/docs)
ReDoc (http://localhost:8088/redoc)
```

---

## 🎯 快速验证部署成功

运行以下命令验证部署：

```bash
# V1 API验证
echo "=== V1 API验证 ==="
curl -s http://localhost:8088/health | jq .
curl -s http://localhost:8088/files/types | jq '.all_types | length'

# Legacy API验证  
echo "=== Legacy API验证 ==="
curl -s http://localhost:8087/health | jq .
curl -s http://localhost:8087/get_supported_file_types | jq '.data.supported_file_types | length'

# 基础服务验证
echo "=== 基础服务验证 ==="
curl -s http://localhost:9000/minio/health/live
psql -h localhost -U postgres -d file_server -c "SELECT 'PostgreSQL连接成功' as status;"
```

如果所有命令都返回正常结果，说明部署成功！ 🎉

---

**💡 提示**: 推荐优先使用V1 RESTful API进行新项目开发，它提供了更好的安全性、标准化和扩展性。Legacy API主要用于现有项目的兼容和迁移。