# Installation Guide

本指南将帮助您在本地环境安装和配置 Unifiles。

## 前置要求

### 系统要求

- **操作系统**: Windows 10+, macOS 10.15+, 或 Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- **Python**: 3.11 或更高版本
- **内存**: 最少 4GB RAM，推荐 8GB+
- **磁盘空间**: 至少 10GB 可用空间

### 依赖服务

Unifiles 需要以下外部服务：

1. **PostgreSQL 15+** with pgvector extension
2. **Redis 7+**
3. **MinIO** (或兼容 S3 的对象存储)

## 安装步骤

### 1. 克隆仓库

```bash
# 使用 HTTPS
git clone https://github.com/ppppangu/Unifiles.git
cd Unifiles

# 或使用 SSH
git clone git@github.com:ppppangu/Unifiles.git
cd Unifiles
```

### 2. 安装 Python 依赖

我们推荐使用 [uv](https://github.com/astral-sh/uv) 作为包管理器，它比 pip 更快更可靠。

#### 安装 uv

**Windows (PowerShell)**:
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 安装项目依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 3. 安装 PostgreSQL 和 pgvector

#### Windows

使用 [EnterpriseDB PostgreSQL](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) 安装器。

安装 pgvector 扩展：
```powershell
# 下载 pgvector for Windows
# 或使用 Docker
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -p 5432:5432 \
  ankane/pgvector
```

#### macOS

```bash
# 使用 Homebrew
brew install postgresql@15
brew install pgvector

# 启动 PostgreSQL
brew services start postgresql@15
```

#### Linux (Ubuntu/Debian)

```bash
# 安装 PostgreSQL
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# 安装 pgvector
sudo apt install postgresql-15-pgvector

# 启动 PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 配置 PostgreSQL

```bash
# 创建数据库
createdb -U postgres unifiles

# 启用扩展
psql -U postgres -d unifiles -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d unifiles -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
```

### 4. 安装 Redis

#### Windows

下载 [Redis for Windows](https://github.com/tporadowski/redis/releases) 或使用 Docker：

```powershell
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

#### macOS

```bash
brew install redis
brew services start redis
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 5. 安装 MinIO

#### 使用 Docker (推荐)

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"
```

#### 本地安装

**Linux/macOS**:
```bash
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
./minio server /data --console-address ":9001"
```

**Windows**:
下载 [MinIO Windows Binary](https://dl.min.io/server/minio/release/windows-amd64/minio.exe) 并运行：

```powershell
.\minio.exe server C:\minio-data --console-address ":9001"
```

### 6. 配置环境变量

复制示例配置文件并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置以下必需变量：

```bash
# 数据库配置
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=unifiles
PG_USER=postgres
PG_PASSWORD=your_database_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_USE_SSL=false

# 安全配置（必需，至少32字符）
SECURITY_SECRET_KEY=your-secret-key-at-least-32-characters-long

# 应用配置
APP_ENV=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO
```

### 7. 初始化数据库

运行数据库迁移脚本：

```bash
# 依次执行 SQL 脚本
psql -U postgres -d unifiles -f scripts/sql/011-create-extensions.sql
psql -U postgres -d unifiles -f scripts/sql/021-create-users.sql
psql -U postgres -d unifiles -f scripts/sql/031-create-file-management.sql
psql -U postgres -d unifiles -f scripts/sql/041-create-extraction.sql
psql -U postgres -d unifiles -f scripts/sql/051-create-knowledge-base.sql
psql -U postgres -d unifiles -f scripts/sql/061-create-components.sql
psql -U postgres -d unifiles -f scripts/sql/071-create-indexes.sql

# 或使用批处理脚本（如果提供）
bash scripts/setup/init_database.sh
```

### 8. 启动应用

#### 开发模式

启动 API 服务器：

```bash
uv run uvicorn unifiles.server.main:app --host 0.0.0.0 --port 8088 --reload
```

启动 Worker（在另一个终端）：

```bash
# Upload Worker
uv run python -m unifiles.workers.upload_worker

# Extraction Worker
uv run python -m unifiles.workers.extraction_worker
```

#### 生产模式

使用 Gunicorn + Uvicorn Workers：

```bash
gunicorn unifiles.server.main:app \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --log-level info
```

### 9. 验证安装

访问以下 URL 验证服务是否正常运行：

- **API 健康检查**: http://localhost:8088/health
- **API 文档**: http://localhost:8088/docs
- **MinIO 控制台**: http://localhost:9001

预期的健康检查响应：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "ok",
    "redis": "ok",
    "minio": "ok"
  }
}
```

## 使用 Docker Compose（推荐）

最简单的方式是使用 Docker Compose 一键启动所有服务：

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

`docker-compose.yml` 已经配置好了所有依赖服务和应用容器。

## 常见问题

### Q: PostgreSQL 连接失败

**A**: 检查以下几点：
1. PostgreSQL 服务是否运行：`systemctl status postgresql` (Linux) 或 `brew services list` (macOS)
2. 连接参数是否正确（主机、端口、用户名、密码）
3. 防火墙是否阻止了 5432 端口
4. PostgreSQL 是否允许本地连接（检查 `pg_hba.conf`）

### Q: MinIO 访问被拒绝

**A**: 确保：
1. MinIO 服务正在运行
2. Access Key 和 Secret Key 正确
3. 如果使用 SSL，确保证书有效
4. 检查 MinIO 的访问策略设置

### Q: Redis 连接超时

**A**: 检查：
1. Redis 服务是否运行：`redis-cli ping` 应返回 `PONG`
2. Redis 配置是否正确
3. 防火墙设置

### Q: 依赖安装失败

**A**: 尝试：
1. 更新 pip/uv：`pip install --upgrade pip` 或 `uv self update`
2. 清理缓存：`uv cache clean`
3. 使用国内镜像源（如果在中国）

### Q: Worker 无法启动

**A**: 确保：
1. Redis 连接正常
2. 所有依赖已安装
3. 环境变量配置正确
4. 检查 Worker 日志获取详细错误信息

## 下一步

- [快速教程](tutorials/first-upload.md) - 学习如何使用 Unifiles
- [API 文档](api-reference.md) - 查看 API 参考
- [开发指南](../CONTRIBUTING.md) - 开始开发

## 获取帮助

如果遇到问题：

1. 查看 [常见问题](faq.md)
2. 搜索 [GitHub Issues](https://github.com/ppppangu/Unifiles/issues)
3. 提交新的 Issue
4. 加入社区讨论群

## 许可证

MIT License
