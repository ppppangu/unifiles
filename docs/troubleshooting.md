# Troubleshooting

本文档帮助你解决使用 Unifiles 时遇到的常见问题。

## 数据库问题

### PostgreSQL 连接失败

**症状**: 启动时报错 `could not connect to server`

**解决方案**:
1. 检查 PostgreSQL 是否运行:
   ```bash
   # Linux/Mac
   sudo systemctl status postgresql
   # Mac (Homebrew)
   brew services list
   ```

2. 检查连接配置:
   - 确认 `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD` 正确
   - 检查防火墙是否阻止 5432 端口

3. 检查 PostgreSQL 配置:
   - 确保 `postgresql.conf` 中 `listen_addresses` 包含你的IP
   - 检查 `pg_hba.conf` 是否允许连接

### pgvector 扩展未安装

**症状**: 启动时报错 `extension "vector" does not exist`

**解决方案**:
```sql
-- 连接到数据库
psql -U postgres -d unifiles

-- 安装扩展
CREATE EXTENSION IF NOT EXISTS vector;
```

## 存储问题

### MinIO 连接失败

**症状**: 文件上传时报错 `S3 connection error`

**解决方案**:
1. 检查 MinIO 是否运行:
   ```bash
   docker ps | grep minio
   ```

2. 验证访问密钥:
   - 确认 `MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY` 正确
   - 尝试通过 MinIO Console (http://localhost:9001) 登录

3. 检查存储桶:
   ```bash
   # 使用 mc (MinIO Client) 检查
   mc alias set myminio http://localhost:9000 minioadmin minioadmin
   mc ls myminio
   ```

### 文件上传失败

**症状**: API 返回 413 或文件上传超时

**解决方案**:
1. 检查文件大小限制（默认 100MB）
2. 增加超时设置:
   ```bash
   UPLOAD_TIMEOUT=300  # 5分钟
   ```
3. 检查磁盘空间

## Redis 问题

### Redis 连接超时

**症状**: 任务队列不工作，日志显示 Redis 连接错误

**解决方案**:
1. 检查 Redis 是否运行:
   ```bash
   redis-cli ping
   # 应该返回 PONG
   ```

2. 检查 Redis 配置:
   ```bash
   # 查看当前连接
   redis-cli CLIENT LIST
   ```

## 性能问题

### API 响应慢

**可能原因**:
- 数据库查询未优化
- 连接池耗尽
- Worker 处理缓慢

**解决方案**:
1. 检查数据库索引:
   ```sql
   -- 查看慢查询
   SELECT * FROM pg_stat_statements
   ORDER BY total_exec_time DESC
   LIMIT 10;
   ```

2. 增加连接池大小:
   ```bash
   PG_POOL_MAX_SIZE=50
   ```

3. 增加 Worker 并发:
   ```bash
   WORKER_CONCURRENCY=8
   ```

### 内存占用高

**解决方案**:
1. 检查 Worker 数量
2. 限制并发任务:
   ```bash
   WORKER_CONCURRENCY=2
   ```
3. 增加服务器内存

## 日志问题

### 找不到日志

**解决方案**:
1. 检查日志级别:
   ```bash
   APP_LOG_LEVEL=DEBUG
   ```

2. 检查日志输出位置:
   - 开发模式: 控制台
   - 生产模式: 日志文件（查看 `LOG_FILE` 配置）

### 日志文件过大

**解决方案**:
配置日志轮转:
```bash
LOG_MAX_SIZE=10485760    # 10MB
LOG_BACKUP_COUNT=5       # 保留5个备份
```

## 获取帮助

如果以上方法都无法解决问题：

1. 查看详细日志:
   ```bash
   APP_LOG_LEVEL=DEBUG uv run uvicorn unifiles.server.main:app
   ```

2. 搜索或提交 GitHub Issue:
   https://github.com/ppppangu/Unifiles/issues

3. 查看 FAQ: [常见问题](faq.md)
