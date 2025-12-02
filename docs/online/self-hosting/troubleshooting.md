# 故障排除

本文档提供常见问题的诊断和解决方案。

## 快速诊断

### 服务状态检查

```bash
# Docker Compose
docker-compose ps
docker-compose logs --tail=50

# Kubernetes
kubectl get pods -n unifiles
kubectl describe pod <pod-name> -n unifiles
```

### 健康检查

```bash
# 基础健康检查
curl http://localhost:8088/health

# 详细健康检查
curl http://localhost:8088/health/detailed | jq
```

### 日志查看

```bash
# Docker
docker-compose logs -f api
docker-compose logs -f worker-upload

# Kubernetes
kubectl logs -n unifiles -l app=unifiles-api -f
```

## 常见问题

### 服务无法启动

#### 症状
```
Container unifiles-api exited with code 1
```

#### 诊断
```bash
# 查看详细日志
docker-compose logs api --tail=100

# 检查配置
docker-compose config

# 检查环境变量
docker-compose exec api env | grep -E "PG_|REDIS_|MINIO_"
```

#### 解决方案

**配置错误**:
```bash
# 验证 .env 文件
cat .env | grep -v "^#" | grep -v "^$"

# 检查必需的变量
required_vars="PG_HOST PG_PASSWORD REDIS_HOST MINIO_ENDPOINT SECURITY_SECRET_KEY"
for var in $required_vars; do
    if [ -z "${!var}" ]; then
        echo "Missing: $var"
    fi
done
```

**依赖服务未就绪**:
```bash
# 确保依赖服务已启动
docker-compose up -d postgres redis minio

# 等待服务就绪
docker-compose exec postgres pg_isready
docker-compose exec redis redis-cli ping
```

---

### 数据库连接失败

#### 症状
```
Connection refused: localhost:5432
asyncpg.exceptions.ConnectionDoesNotExistError
```

#### 诊断
```bash
# 检查 PostgreSQL 状态
docker-compose exec postgres pg_isready

# 测试连接
docker-compose exec api python -c "
import asyncpg
import asyncio
asyncio.run(asyncpg.connect(
    host='postgres',
    database='unifiles',
    user='unifiles',
    password='your_password'
))
print('Connection OK')
"

# 检查网络
docker network inspect unifiles_default
```

#### 解决方案

**认证失败**:
```bash
# 检查用户和密码
docker-compose exec postgres psql -U postgres -c "\du"

# 重置密码
docker-compose exec postgres psql -U postgres -c "
ALTER USER unifiles WITH PASSWORD 'new_password';
"
```

**连接数耗尽**:
```sql
-- 检查连接数
SELECT count(*) FROM pg_stat_activity WHERE datname = 'unifiles';

-- 终止空闲连接
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'unifiles' 
  AND state = 'idle' 
  AND state_change < NOW() - INTERVAL '10 minutes';
```

**pg_hba.conf 配置**:
```bash
# 检查认证配置
docker-compose exec postgres cat /var/lib/postgresql/data/pg_hba.conf

# 添加允许的连接
# host unifiles unifiles 0.0.0.0/0 md5
```

---

### Redis 连接问题

#### 症状
```
Connection refused: redis:6379
NOAUTH Authentication required
```

#### 诊断
```bash
# 检查 Redis 状态
docker-compose exec redis redis-cli ping

# 带密码测试
docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping

# 检查内存使用
docker-compose exec redis redis-cli -a $REDIS_PASSWORD INFO memory
```

#### 解决方案

**认证问题**:
```bash
# 检查密码配置
docker-compose exec redis redis-cli CONFIG GET requirepass

# 设置密码
docker-compose exec redis redis-cli CONFIG SET requirepass "new_password"
```

**内存不足**:
```bash
# 检查内存策略
docker-compose exec redis redis-cli -a $REDIS_PASSWORD CONFIG GET maxmemory-policy

# 设置内存限制和策略
docker-compose exec redis redis-cli -a $REDIS_PASSWORD CONFIG SET maxmemory 2gb
docker-compose exec redis redis-cli -a $REDIS_PASSWORD CONFIG SET maxmemory-policy allkeys-lru
```

---

### MinIO/存储问题

#### 症状
```
S3 error: Access Denied
Connection refused: minio:9000
```

#### 诊断
```bash
# 检查 MinIO 状态
docker-compose exec minio mc admin info local

# 测试连接
docker-compose exec api python -c "
from minio import Minio
client = Minio('minio:9000', 'unifiles', 'your_secret', secure=False)
print(client.list_buckets())
"

# 检查 Bucket
docker-compose exec minio mc ls local
```

#### 解决方案

**Bucket 不存在**:
```bash
# 创建 Bucket
docker-compose exec minio mc mb local/unifiles-raw
docker-compose exec minio mc mb local/unifiles-processed
```

**权限问题**:
```bash
# 检查策略
docker-compose exec minio mc admin policy list local

# 重置用户权限
docker-compose exec minio mc admin user add local unifiles your_secret
docker-compose exec minio mc admin policy attach local readwrite --user unifiles
```

**磁盘空间**:
```bash
# 检查磁盘使用
docker-compose exec minio mc admin info local --json | jq '.info.backend'

# 清理临时文件
docker-compose exec minio mc rm --recursive --force local/unifiles-cache/
```

---

### 文件上传失败

#### 症状
```
413 Request Entity Too Large
File type not allowed
Upload timeout
```

#### 诊断
```bash
# 检查上传日志
docker-compose logs api | grep -i upload

# 测试上传
curl -v -X POST http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@test.pdf"
```

#### 解决方案

**文件过大**:
```bash
# 检查配置
echo $MAX_UPLOAD_SIZE_MB

# Nginx 配置
# client_max_body_size 100M;
```

**文件类型限制**:
```bash
# 检查允许的类型
echo $ALLOWED_FILE_TYPES

# 添加新类型
ALLOWED_FILE_TYPES=pdf,docx,xlsx,pptx,txt,md,html,csv
```

**超时问题**:
```bash
# 增加超时时间
# nginx.conf
# proxy_read_timeout 300;
# proxy_connect_timeout 300;
```

---

### 内容提取失败

#### 症状
```
Extraction status: failed
OCR timeout
Memory error during processing
```

#### 诊断
```bash
# 检查提取 Worker
docker-compose logs worker-extraction | tail -100

# 检查队列状态
docker-compose exec redis redis-cli -a $REDIS_PASSWORD LLEN extraction_queue

# 检查文件状态
curl http://localhost:8088/api/v1/files/$FILE_ID \
  -H "Authorization: Bearer $API_KEY"
```

#### 解决方案

**OCR 超时**:
```bash
# 增加超时时间
OCR_TIMEOUT_SECONDS=600

# 重试提取
curl -X POST http://localhost:8088/api/v1/extractions \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"file_id": "xxx", "mode": "simple"}'
```

**内存不足**:
```yaml
# 增加 Worker 内存限制
services:
  worker-extraction:
    deploy:
      resources:
        limits:
          memory: 8G
```

---

### 搜索结果为空

#### 症状
```
Search returns empty results
Vector similarity always 0
```

#### 诊断
```sql
-- 检查向量索引状态
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chunks';

-- 检查数据
SELECT count(*) FROM chunks WHERE knowledge_base_id = 'xxx';

-- 检查向量维度
SELECT embedding::text FROM chunks LIMIT 1;
```

#### 解决方案

**索引未创建**:
```sql
-- 创建 HNSW 索引
CREATE INDEX CONCURRENTLY idx_chunks_embedding ON chunks 
    USING hnsw (embedding vector_cosine_ops);
```

**维度不匹配**:
```bash
# 检查嵌入模型配置
echo $EMBEDDING_MODEL
echo $EMBEDDING_DIMENSIONS

# 重新生成嵌入 (需要重建知识库)
```

**数据未索引**:
```bash
# 触发重新索引
curl -X POST http://localhost:8088/api/v1/knowledge-bases/$KB_ID/reindex \
  -H "Authorization: Bearer $API_KEY"
```

---

### 性能问题

#### 症状
```
High latency
Timeout errors
Slow search
```

#### 诊断
```bash
# 检查资源使用
docker stats

# 检查慢查询
docker-compose exec postgres psql -U unifiles -d unifiles -c "
SELECT query, calls, mean_exec_time, total_exec_time 
FROM pg_stat_statements 
ORDER BY total_exec_time DESC 
LIMIT 10;
"

# 检查连接池
curl http://localhost:8088/metrics | grep pool
```

#### 解决方案

**数据库慢查询**:
```sql
-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM chunks 
WHERE knowledge_base_id = 'xxx' 
ORDER BY embedding <=> '[...]'::vector 
LIMIT 10;

-- 更新统计信息
ANALYZE chunks;

-- 调整索引参数
SET hnsw.ef_search = 100;
```

**连接池耗尽**:
```bash
# 增加连接池大小
PG_POOL_MAX=50

# 检查连接泄漏
SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction';
```

**扩容**:
```bash
# 增加 API 实例
docker-compose up -d --scale api=3
```

---

### Worker 队列积压

#### 症状
```
Queue size growing
Tasks not being processed
```

#### 诊断
```bash
# 检查队列大小
docker-compose exec redis redis-cli -a $REDIS_PASSWORD LLEN upload_queue
docker-compose exec redis redis-cli -a $REDIS_PASSWORD LLEN extraction_queue

# 检查 Worker 状态
docker-compose ps | grep worker
docker-compose logs worker-upload --tail=50
```

#### 解决方案

**Worker 异常**:
```bash
# 重启 Worker
docker-compose restart worker-upload worker-extraction
```

**增加 Worker 数量**:
```bash
docker-compose up -d --scale worker-upload=4 --scale worker-extraction=4
```

**清理死信队列**:
```bash
docker-compose exec redis redis-cli -a $REDIS_PASSWORD DEL dead_letter_queue
```

## 日志分析

### 常见错误模式

```bash
# 搜索错误日志
docker-compose logs api 2>&1 | grep -i error | tail -50

# 统计错误类型
docker-compose logs api 2>&1 | grep -i error | \
  sed 's/.*ERROR.*| //' | sort | uniq -c | sort -rn
```

### 关键日志位置

| 组件 | 日志位置 |
|------|---------|
| API | `docker-compose logs api` |
| Worker | `docker-compose logs worker-*` |
| PostgreSQL | `docker-compose logs postgres` |
| Redis | `docker-compose logs redis` |
| MinIO | `docker-compose logs minio` |

## 获取帮助

### 收集诊断信息

```bash
#!/bin/bash
# collect_diagnostics.sh

OUTPUT="diagnostics_$(date +%Y%m%d_%H%M%S)"
mkdir -p $OUTPUT

# 系统信息
uname -a > $OUTPUT/system.txt
df -h >> $OUTPUT/system.txt
free -m >> $OUTPUT/system.txt

# Docker 信息
docker version > $OUTPUT/docker.txt
docker-compose ps >> $OUTPUT/docker.txt
docker stats --no-stream >> $OUTPUT/docker.txt

# 服务日志
docker-compose logs --tail=500 > $OUTPUT/logs.txt

# 配置 (隐藏敏感信息)
docker-compose config | sed 's/password:.*/password: [REDACTED]/' > $OUTPUT/config.txt

# 健康检查
curl -s http://localhost:8088/health/detailed > $OUTPUT/health.json

# 打包
tar -czf ${OUTPUT}.tar.gz $OUTPUT
rm -rf $OUTPUT

echo "Diagnostics collected: ${OUTPUT}.tar.gz"
```

### 报告问题

在报告问题时，请提供:

1. Unifiles 版本
2. 部署方式 (Docker/Kubernetes)
3. 错误消息和日志
4. 复现步骤
5. 诊断信息包

GitHub Issues: https://github.com/your-org/unifiles/issues

## 下一步

- [可观测性](./observability.md) - 设置监控告警
- [升级指南](./upgrade.md) - 升级相关问题
- [备份与恢复](./backup-restore.md) - 数据恢复
