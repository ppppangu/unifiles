# 数据库设置

本文档详细介绍 PostgreSQL 和 pgvector 的安装、配置和优化。

## PostgreSQL 安装

### Docker 方式 (推荐)

```bash
# 使用预装 pgvector 的镜像
docker run -d \
  --name unifiles-postgres \
  -e POSTGRES_USER=unifiles \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=unifiles \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg15
```

### 手动安装

#### Ubuntu/Debian

```bash
# 安装 PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# 安装 pgvector
sudo apt install postgresql-15-pgvector

# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### CentOS/RHEL

```bash
# 添加 PostgreSQL 仓库
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 安装 PostgreSQL 15
sudo dnf install -y postgresql15-server postgresql15-contrib

# 初始化
sudo /usr/pgsql-15/bin/postgresql-15-setup initdb

# 安装 pgvector
sudo dnf install -y pgvector_15

# 启动服务
sudo systemctl start postgresql-15
sudo systemctl enable postgresql-15
```

#### macOS

```bash
# 使用 Homebrew
brew install postgresql@15
brew install pgvector

# 启动服务
brew services start postgresql@15
```

## 数据库初始化

### 创建数据库和用户

```sql
-- 连接到 PostgreSQL
sudo -u postgres psql

-- 创建用户
CREATE USER unifiles WITH PASSWORD 'your_secure_password';

-- 创建数据库
CREATE DATABASE unifiles OWNER unifiles;

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE unifiles TO unifiles;

-- 切换到 unifiles 数据库
\c unifiles

-- 安装扩展 (需要超级用户权限)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 授予扩展使用权限
GRANT USAGE ON SCHEMA public TO unifiles;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO unifiles;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO unifiles;
```

### 运行迁移脚本

```bash
# 按顺序执行迁移
for f in scripts/sql/*.sql; do
    echo "Running $f..."
    psql -U unifiles -d unifiles -f "$f"
done
```

或使用应用内置命令:

```bash
python -m unifiles.scripts.migrate
```

## PostgreSQL 配置优化

### 编辑 postgresql.conf

```ini
# /etc/postgresql/15/main/postgresql.conf

# === 连接设置 ===
listen_addresses = '*'
max_connections = 200
superuser_reserved_connections = 3

# === 内存设置 ===
# 建议: 总内存的 25%
shared_buffers = 4GB

# 建议: 总内存的 50-75%
effective_cache_size = 12GB

# 建议: shared_buffers 的 25%
maintenance_work_mem = 1GB

# 每个连接的工作内存
work_mem = 64MB

# === WAL 设置 ===
wal_level = replica
max_wal_size = 4GB
min_wal_size = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 64MB

# === 查询优化 ===
random_page_cost = 1.1  # SSD 存储
effective_io_concurrency = 200  # SSD 存储
default_statistics_target = 100

# === 并行查询 ===
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
parallel_tuple_cost = 0.01
parallel_setup_cost = 500

# === 日志设置 ===
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000  # 记录超过 1 秒的查询
log_line_prefix = '%t [%p] %u@%d '
```

### 配置 pg_hba.conf

```
# /etc/postgresql/15/main/pg_hba.conf

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# 本地连接
local   all             postgres                                peer
local   all             unifiles                                md5

# IPv4 本地连接
host    all             all             127.0.0.1/32            md5

# 内网连接 (根据实际网段调整)
host    unifiles        unifiles        10.0.0.0/8              md5
host    unifiles        unifiles        172.16.0.0/12           md5
host    unifiles        unifiles        192.168.0.0/16          md5

# 禁止外网直接访问
# host  all             all             0.0.0.0/0               reject
```

### 应用配置

```bash
# 重新加载配置
sudo systemctl reload postgresql

# 或重启服务
sudo systemctl restart postgresql
```

## pgvector 优化

### 索引配置

```sql
-- 检查 pgvector 版本
SELECT extversion FROM pg_extension WHERE extname = 'vector';

-- HNSW 索引 (推荐，pgvector 0.5.0+)
-- m: 每层连接数 (越大越精确，越慢)
-- ef_construction: 构建时搜索范围
CREATE INDEX idx_chunks_embedding_hnsw ON chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 设置查询时的 ef_search
SET hnsw.ef_search = 100;

-- IVFFlat 索引 (适合大规模数据)
-- lists: 聚类数量，建议 sqrt(n)
CREATE INDEX idx_chunks_embedding_ivf ON chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 设置查询时的 probes
SET ivfflat.probes = 10;
```

### 向量维度选择

```sql
-- 1536 维 (OpenAI text-embedding-3-small)
ALTER TABLE chunks ADD COLUMN embedding vector(1536);

-- 3072 维 (OpenAI text-embedding-3-large)
ALTER TABLE chunks ADD COLUMN embedding_large vector(3072);

-- 1024 维 (本地模型如 BGE)
ALTER TABLE chunks ADD COLUMN embedding_local vector(1024);
```

### 距离函数选择

```sql
-- 余弦距离 (推荐，归一化向量)
SELECT * FROM chunks ORDER BY embedding <=> query_vector LIMIT 10;

-- 欧氏距离
SELECT * FROM chunks ORDER BY embedding <-> query_vector LIMIT 10;

-- 内积 (需要归一化向量)
SELECT * FROM chunks ORDER BY embedding <#> query_vector LIMIT 10;
```

## 高可用配置

### 主从复制

#### 主节点配置

```ini
# postgresql.conf
wal_level = replica
max_wal_senders = 5
wal_keep_size = 1GB
hot_standby = on
```

```
# pg_hba.conf
host    replication     replicator      SLAVE_IP/32            md5
```

```sql
-- 创建复制用户
CREATE USER replicator WITH REPLICATION PASSWORD 'replica_password';
```

#### 从节点配置

```bash
# 停止从节点
sudo systemctl stop postgresql

# 清空数据目录
sudo rm -rf /var/lib/postgresql/15/main/*

# 从主节点复制
sudo -u postgres pg_basebackup -h MASTER_IP -D /var/lib/postgresql/15/main \
  -U replicator -P -v -R -X stream
```

```ini
# postgresql.conf
hot_standby = on
```

### 连接池 (PgBouncer)

```ini
# /etc/pgbouncer/pgbouncer.ini

[databases]
unifiles = host=localhost port=5432 dbname=unifiles

[pgbouncer]
listen_addr = *
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
```

```
# /etc/pgbouncer/userlist.txt
"unifiles" "md5_hashed_password"
```

## 备份策略

### 逻辑备份 (pg_dump)

```bash
# 完整备份
pg_dump -U unifiles -d unifiles -F c -f backup_$(date +%Y%m%d).dump

# 仅 schema
pg_dump -U unifiles -d unifiles -s -f schema.sql

# 定时备份 (crontab)
0 2 * * * /usr/bin/pg_dump -U unifiles -d unifiles -F c -f /backups/unifiles_$(date +\%Y\%m\%d).dump
```

### 物理备份 (pg_basebackup)

```bash
# 完整物理备份
pg_basebackup -U unifiles -D /backups/base_$(date +%Y%m%d) -Ft -z -P
```

### 恢复

```bash
# 从逻辑备份恢复
pg_restore -U unifiles -d unifiles -c backup.dump

# 从物理备份恢复
# 1. 停止 PostgreSQL
# 2. 清空数据目录
# 3. 解压备份
# 4. 启动 PostgreSQL
```

## 监控查询

```sql
-- 数据库大小
SELECT pg_size_pretty(pg_database_size('unifiles'));

-- 表大小
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 索引使用情况
SELECT 
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 活动连接
SELECT 
    datname,
    usename,
    state,
    count(*)
FROM pg_stat_activity
GROUP BY datname, usename, state;

-- 慢查询
SELECT 
    query,
    calls,
    total_exec_time / 1000 as total_sec,
    mean_exec_time / 1000 as mean_sec
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## 故障排除

### 连接问题

```bash
# 测试连接
psql -h localhost -U unifiles -d unifiles -c "SELECT 1"

# 检查服务状态
sudo systemctl status postgresql

# 查看日志
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### 性能问题

```sql
-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM chunks 
WHERE knowledge_base_id = 'xxx' 
ORDER BY embedding <=> '[...]'::vector 
LIMIT 10;

-- 更新统计信息
ANALYZE chunks;

-- 重建索引
REINDEX INDEX idx_chunks_embedding_hnsw;
```

## 下一步

- [存储设置](./storage-setup.md) - MinIO 配置
- [可观测性](./observability.md) - 数据库监控
- [备份与恢复](./backup-restore.md) - 完整备份策略
