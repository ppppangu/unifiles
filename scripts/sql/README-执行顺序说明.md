# 数据库建表SQL文件执行顺序说明

## 概述

本文档详细说明了基于组件抽象设计的数据库建表SQL文件的执行顺序和相关注意事项。所有SQL文件都位于 `数据库建表逻辑/new/` 目录下，按照数字序号命名，确保正确的执行顺序。

## 文件列表和执行顺序

### 第一步：扩展和基础设置
**文件**: `011-create-extensions.sql`
**描述**: 创建PostgreSQL必要的扩展插件和基础设置
**包含内容**:
- 向量化扩展（pgvector）
- 全文搜索扩展（rum）
- 数据结构扩展（ltree）
- 创建主要数据库模式（chunk_schema）

**执行命令**:
```bash
psql -d your_database -f 011-create-extensions.sql
```

### 第二步：用户和权限管理
**文件**: `021-create-users.sql`
**描述**: 创建用户和权限管理表
**包含内容**:
- 用户表（users）
- 用户操作日志表（user_activity_logs）
- 相关触发器和初始数据

**依赖**: 必须在扩展创建后执行
**执行命令**:
```bash
psql -d your_database -f 021-create-users.sql
```

### 第三步：文件管理层
**文件**: `031-create-file-management.sql`
**描述**: 创建文件管理层表结构
**包含内容**:
- 文件表（files）
- 文件处理日志表（file_processing_logs）


**依赖**: 必须在用户表创建后执行
**执行命令**:
```bash
psql -d your_database -f 031-create-file-management.sql
```

### 第四步：内容提取层
**文件**: `041-create-content-extraction.sql`
**描述**: 创建内容提取层表结构
**包含内容**:
- 提取文档表（extracted_documents）
- 提取资源表（extracted_assets）
- 提取错误日志表（extraction_logs）

**依赖**: 必须在文件管理表创建后执行
**执行命令**:
```bash
psql -d your_database -f 041-create-content-extraction.sql
```

### 第五步：知识库层
**文件**: `051-create-knowledge-base.sql`
**描述**: 创建知识库层表结构
**包含内容**:
- 知识库表（knowledge_bases）
- 知识库文档表（documents）
- 知识库统计表（kb_statistics）

**依赖**: 必须在内容提取表创建后执行
**执行命令**:
```bash
psql -d your_database -f 051-create-knowledge-base.sql
```

### 第六步：组件抽象层
**文件**: `061-create-component-abstraction.sql`
**描述**: 创建组件抽象层表结构（核心设计）
**包含内容**:
- 组件抽象表（components）
- 文本块子类表（chunks）
- 图片块子类表（photos）

**依赖**: 必须在知识库表创建后执行
**执行命令**:
```bash
psql -d your_database -f 061-create-component-abstraction.sql
```

### 第七步：索引和性能优化
**文件**: `071-create-indexes.sql`
**描述**: 创建数据库索引和性能优化
**包含内容**:
- 所有表的查询优化索引
- 向量搜索索引（IVFFlat）
- 全文搜索索引
- 复合索引和分析索引
- 索引监控视图

**依赖**: 必须在所有表创建后执行
**执行命令**:
```bash
psql -d your_database -f 071-create-indexes.sql
```

### 第八步：触发器和自动化
**文件**: `081-create-triggers.sql`
**描述**: 创建触发器和自动化逻辑
**包含内容**:
- 数据同步触发器
- 全文搜索触发器
- 审计触发器
- 业务逻辑触发器
- 触发器管理函数

**依赖**: 必须在所有表和索引创建后执行
**执行命令**:
```bash
psql -d your_database -f 081-create-triggers.sql
```

## 完整执行脚本

### 方法一：逐个执行（推荐用于生产环境）

```bash
#!/bin/bash
DB_NAME="your_database_name"
SQL_DIR="数据库建表逻辑/new"

echo "开始执行数据库建表SQL文件..."

# 第一步：扩展和基础设置
echo "执行第一步：扩展和基础设置"
psql -d $DB_NAME -f "$SQL_DIR/011-create-extensions.sql"
if [ $? -ne 0 ]; then
    echo "错误：扩展创建失败"
    exit 1
fi

# 第二步：用户和权限管理
echo "执行第二步：用户和权限管理"
psql -d $DB_NAME -f "$SQL_DIR/021-create-users.sql"
if [ $? -ne 0 ]; then
    echo "错误：用户表创建失败"
    exit 1
fi

# 第三步：文件管理层
echo "执行第三步：文件管理层"
psql -d $DB_NAME -f "$SQL_DIR/031-create-file-management.sql"
if [ $? -ne 0 ]; then
    echo "错误：文件管理表创建失败"
    exit 1
fi

# 第四步：内容提取层
echo "执行第四步：内容提取层"
psql -d $DB_NAME -f "$SQL_DIR/041-create-content-extraction.sql"
if [ $? -ne 0 ]; then
    echo "错误：内容提取表创建失败"
    exit 1
fi

# 第五步：知识库层
echo "执行第五步：知识库层"
psql -d $DB_NAME -f "$SQL_DIR/051-create-knowledge-base.sql"
if [ $? -ne 0 ]; then
    echo "错误：知识库表创建失败"
    exit 1
fi

# 第六步：组件抽象层
echo "执行第六步：组件抽象层"
psql -d $DB_NAME -f "$SQL_DIR/061-create-component-abstraction.sql"
if [ $? -ne 0 ]; then
    echo "错误：组件抽象表创建失败"
    exit 1
fi

# 第七步：索引和性能优化
echo "执行第七步：索引和性能优化"
psql -d $DB_NAME -f "$SQL_DIR/071-create-indexes.sql"
if [ $? -ne 0 ]; then
    echo "错误：索引创建失败"
    exit 1
fi

# 第八步：触发器和自动化
echo "执行第八步：触发器和自动化"
psql -d $DB_NAME -f "$SQL_DIR/081-create-triggers.sql"
if [ $? -ne 0 ]; then
    echo "错误：触发器创建失败"
    exit 1
fi

echo "数据库建表完成！"
```

### 方法二：批量执行（适用于开发环境）

```bash
#!/bin/bash
DB_NAME="your_database_name"
SQL_DIR="数据库建表逻辑/new"

# 按顺序执行所有SQL文件
for file in "$SQL_DIR"/{011,021,031,041,051,061,071,081}-*.sql; do
    if [ -f "$file" ]; then
        echo "执行文件: $(basename $file)"
        psql -d $DB_NAME -f "$file"
        if [ $? -ne 0 ]; then
            echo "错误：执行 $(basename $file) 失败"
            exit 1
        fi
    fi
done

echo "数据库建表完成！"
```

## 重要注意事项

### 1. 执行环境要求
- PostgreSQL 版本：推荐 14.0 或更高版本
- 必需的扩展：pgvector、ltree、rum
- 数据库权限：需要超级用户或具有CREATE权限的用户

### 2. 扩展依赖检查
在执行之前，请确保以下扩展可用：
```sql
-- 检查扩展是否可用
SELECT name, default_version, installed_version 
FROM pg_available_extensions 
WHERE name IN ('vector', 'ltree', 'rum');
```

### 3. 内存和性能配置
建议的PostgreSQL配置调整：
```ini
# postgresql.conf
shared_preload_libraries = 'vector'
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# 向量搜索相关
vector.lists = 100
vector.hnsw_ef_search = 64
```

### 4. 数据验证
执行完成后，验证表结构：
```sql
-- 检查所有表是否创建成功
SELECT schemaname, tablename, tableowner 
FROM pg_tables 
WHERE schemaname = 'chunk_schema'
ORDER BY tablename;

-- 检查索引是否创建成功
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'chunk_schema'
ORDER BY tablename, indexname;

-- 检查触发器是否创建成功
SELECT * FROM chunk_schema.trigger_status;
```

### 5. 回滚方案
如果需要回滚，按相反顺序执行：
```sql
-- 删除整个schema（谨慎使用）
DROP SCHEMA IF EXISTS chunk_schema CASCADE;

-- 或者逐个删除表
-- 注意：由于有外键依赖，需要按相反的创建顺序删除
```

## 性能优化建议

### 1. 批量数据导入时的优化
```sql
-- 导入大量数据前，禁用触发器
SELECT chunk_schema.disable_stats_triggers();
SELECT chunk_schema.disable_audit_triggers();

-- 导入数据...

-- 导入完成后，重新启用触发器
SELECT chunk_schema.enable_stats_triggers();
SELECT chunk_schema.enable_audit_triggers();

-- 手动更新统计信息
ANALYZE;
```

### 2. 向量索引优化
```sql
-- 创建向量索引后，根据数据量调整参数
ALTER INDEX idx_components_embedding SET (lists = 1000);  -- 适用于大数据集
```

### 3. 定期维护
```sql
-- 定期清理和重建索引
REINDEX SCHEMA chunk_schema;

-- 更新表统计信息
ANALYZE chunk_schema.components;
ANALYZE chunk_schema.chunks;
ANALYZE chunk_schema.photos;
```

## 监控和维护

### 1. 性能监控查询
```sql
-- 查看索引使用情况
SELECT * FROM chunk_schema.index_usage_stats WHERE usage_level = 'UNUSED';

-- 查看向量索引统计
SELECT * FROM chunk_schema.vector_index_stats;

-- 查看表大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'chunk_schema'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 2. 定期清理任务
```sql
-- 清理旧的处理日志
DELETE FROM chunk_schema.file_processing_logs 
WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
AND status IN ('completed', 'failed');

-- 清理旧的活动日志
DELETE FROM chunk_schema.user_activity_logs 
WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
```

## 联系和支持

如果在执行过程中遇到问题，请检查：
1. PostgreSQL错误日志
2. 扩展依赖是否满足
3. 数据库权限是否正确
4. 文件路径是否正确

执行完成后，数据库将支持完整的文件上传、内容提取、知识库管理和组件抽象功能。