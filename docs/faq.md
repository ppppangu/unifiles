# FAQ (常见问题)

## 一般问题

### Unifiles 是什么？

Unifiles 是一个统一的文件处理与知识库管理平台，支持多种文件格式的上传、内容提取和语义检索。

### Unifiles 支持哪些文件格式？

目前支持：
- 文档: PDF, Word (docx), PPT (pptx), Excel (xlsx)
- 图片: PNG, JPEG, WebP
- 文本: TXT, Markdown

### Unifiles 是免费的吗？

Unifiles 是开源项目，采用 MIT 许可证，可以免费使用和修改。

## 使用问题

### 如何上传文件？

使用 API 上传文件：

```bash
curl -X POST http://localhost:8088/files   -H "Authorization: Bearer [REDACTED]"   -F "file=@document.pdf"
```

详见[快速开始](quickstart.md)。

### 如何获取 API Key？

创建 API Key：

```sql
-- 连接数据库
psql -U postgres -d unifiles

-- 创建用户
INSERT INTO unifiles.users (id) VALUES ('your_user_id');

-- 创建 API Key
INSERT INTO unifiles.access_keys (user_id, name)
VALUES ('your_user_id', 'My API Key');

-- 获取生成的 key
SELECT access_key FROM unifiles.access_keys
WHERE user_id = 'your_user_id'
ORDER BY created_at DESC LIMIT 1;
```

### 支持哪些 OCR 引擎？

目前支持：
- Mistral Pixtral (推荐)
- Tesseract OCR
- 自定义 OCR 提供商

### 如何创建知识库？

```bash
curl -X POST http://localhost:8088/knowledge-bases   -H "Authorization: Bearer [REDACTED]"   -H "Content-Type: application/json"   -d '{"name": "My Knowledge Base"}'
```

### 知识库支持哪些搜索方式？

- 向量语义搜索
- 关键词搜索
- 混合搜索（向量 + 关键词）

## 技术问题

### Unifiles 使用什么技术栈？

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL + pgvector
- **Storage**: MinIO
- **Cache/Queue**: Redis
- **Package Manager**: uv

### 最低系统要求是什么？

- CPU: 2核
- 内存: 4GB (推荐 8GB+)
- 磁盘: 10GB+
- Python: 3.11+

### 支持水平扩展吗？

是的，Unifiles 采用无状态设计，支持：
- API 服务器水平扩展
- Worker 水平扩展
- 数据库读写分离
- 对象存储分布式部署

### 如何备份数据？

备份包含以下部分：

1. PostgreSQL 数据库:
   ```bash
   pg_dump -U postgres unifiles > backup.sql
   ```

2. MinIO 对象存储:
   ```bash
   mc mirror myminio/unifiles /backup/unifiles-storage
   ```

## 部署问题

### 可以部署在哪些平台？

支持以下平台：
- Docker / Docker Compose
- Kubernetes
- 云平台 (AWS, Azure, GCP)
- 自托管服务器

### 推荐的生产配置是什么？

- API 服务器: 4核 8GB x 2 实例
- Worker: 2核 4GB x 3 实例
- PostgreSQL: 4核 16GB + SSD
- Redis: 2核 4GB
- MinIO: 根据存储需求配置

详见[部署指南](deployment.md)。

### 如何监控服务健康？

访问健康检查端点：
```bash
curl http://localhost:8088/health
```

返回示例：
```json
{
  "status": "healthy",
  "services": {
    "database": "ok",
    "redis": "ok",
    "minio": "ok"
  }
}
```

## 安全问题

### API 如何认证？

使用 Bearer Token 认证：
```bash
Authorization: Bearer [REDACTED]
```

### 支持 HTTPS 吗？

是的，在生产环境建议：
- 使用 Nginx/Caddy 作为反向代理
- 配置 SSL 证书
- 启用 HSTS

### 数据是否加密？

- 传输加密: 支持 HTTPS/TLS
- 存储加密: 支持 MinIO 服务器端加密
- 数据库加密: 支持 PostgreSQL 透明数据加密

## 开发问题

### 如何贡献代码？

查看[贡献指南](../CONTRIBUTING.md)。

### 如何运行测试？

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/integration/

# 查看覆盖率
uv run pytest --cov=unifiles
```

### 如何调试？

1. 启用调试模式:
   ```bash
   APP_DEBUG=true APP_LOG_LEVEL=DEBUG uv run uvicorn unifiles.server.main:app
   ```

2. 使用断点:
   ```python
   import pdb; pdb.set_trace()
   ```

## 更多问题？

- 查看[故障排查](troubleshooting.md)
- 提交 [GitHub Issue](https://github.com/ppppangu/Unifiles/issues)
- 查看[完整文档](https://unifiles.dev/docs)
