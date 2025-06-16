# delete_file_from_vcdb 函数设计文档

## 概述

`delete_file_from_vcdb` 函数用于从向量数据库中删除文件及其所有相关数据。该函数基于对数据库建表逻辑和触发器机制的深入理解，采用最优的删除策略。

## 数据库架构理解

### 层次结构

```
Users (用户)
  ↓ 1:N
Knowledge Bases (知识库)  
  ↓ 1:N
Documents (文档)
  ↓ 1:N  
Components (组件)
  ↓ 1:1
Chunks/Photos (文本块/图片)
```

### 关键表结构

#### 1. chunk_schema.users

```sql
CREATE TABLE chunk_schema.users(
    id TEXT PRIMARY KEY,
    knowledge_ids TEXT[] DEFAULT '{}'
);
```

#### 2. chunk_schema.knowledge_bases

```sql
CREATE TABLE chunk_schema.knowledge_bases (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    document_ids TEXT[] DEFAULT '{}'::TEXT[]
);
```

#### 3. chunk_schema.documents

```sql
CREATE TABLE chunk_schema.documents (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES chunk_schema.knowledge_bases(id) ON DELETE CASCADE,
    name TEXT,
    text TEXT,
    component_ids TEXT[] DEFAULT '{}',
    hierarchy_path ltree DEFAULT 'root'::ltree
);
```

#### 4. chunk_schema.components

```sql
CREATE TABLE chunk_schema.components (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    doc_position INTEGER NOT NULL,
    type TEXT CHECK (type IN ('chunk','photo','table')),
    text TEXT,
    embedding vector,
    tsv tsvector,
    UNIQUE (document_id, doc_position)
);
```

#### 5. chunk_schema.chunks & chunk_schema.photos

```sql
CREATE TABLE chunk_schema.chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    text TEXT,
    embedding vector,
    doc_position INTEGER
);

CREATE TABLE chunk_schema.photos (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    type TEXT CHECK (type IN ('photo','table')),
    text TEXT,
    base64_image TEXT,
    embedding vector,
    doc_position INTEGER
);
```

## 触发器机制理解

### 1. 级联删除 (ON DELETE CASCADE)

当删除documents表中的记录时，PostgreSQL会自动：

- 删除所有 `components` 表中 `document_id` 匹配的记录
- 删除所有 `chunks` 表中 `document_id` 匹配的记录
- 删除所有 `photos` 表中 `document_id` 匹配的记录

### 2. 触发器自动更新

根据 `022-create-chunk-trigger-index.sql`，存在以下触发器：

#### document_after_trigger

```sql
CREATE TRIGGER document_after_trigger
AFTER INSERT OR UPDATE ON chunk_schema.documents
FOR EACH ROW EXECUTE FUNCTION update_knowledge_base_document_ids();
```

当documents表发生DELETE操作时，触发器会：

- 从 `knowledge_bases.document_ids` 数组中移除被删除的document_id
- 保持知识库索引数组与实际文档的一致性

## 函数设计原理

### 1. 权限验证策略

```sql
-- 验证知识库所有权
SELECT id FROM chunk_schema.knowledge_bases 
WHERE id = $1 AND user_id = $2

-- 验证文档归属
SELECT id FROM chunk_schema.documents 
WHERE id = $1 AND knowledge_base_id = $2
```

### 2. 删除策略

**核心原则：只删除documents表记录，让触发器处理其余工作**

```sql
DELETE FROM chunk_schema.documents 
WHERE id = $1 AND knowledge_base_id = $2
```

### 3. 自动化处理流程

1. **级联删除**：PostgreSQL自动删除所有相关的components、chunks、photos
2. **数组更新**：触发器自动从knowledge_bases.document_ids中移除document_id
3. **数据一致性**：确保没有孤立记录，所有引用关系保持正确

## 函数实现特点

### 1. 事务安全

```python
async with conn.transaction():
    # 所有操作在单个事务中执行
    # 确保原子性：要么全部成功，要么全部回滚
```

### 2. 分层验证

```python
# 第一层：验证知识库所有权
kb_result = await conn.fetchrow(kb_check_query, knowledge_base_id, user_id)

# 第二层：验证文档归属  
doc_result = await conn.fetchrow(doc_check_query, file_id, knowledge_base_id)
```

### 3. 详细日志

```python
# 记录删除操作
logger.info(f"Successfully deleted document from vector database...")

# 记录触发器自动处理
logger.info(f"Database triggers automatically handled: 1) Cascade deleted...; 2) Updated...")
```

## 优势分析

### 1. 数据一致性

- 利用数据库级别的约束和触发器
- 避免手动删除多个表可能导致的不一致

### 2. 代码简洁性

- 只需一条DELETE语句
- 触发器自动处理复杂的级联操作

### 3. 性能优化

- 数据库级别的批量操作比应用层循环删除更高效
- 减少网络往返次数

### 4. 错误处理

- 完整的异常捕获和分类
- 详细的错误日志记录

## 使用示例

```python
# 基本用法
try:
    success = await delete_file_from_vcdb(
        user_id="user_123",
        file_id="doc_456", 
        knowledge_base_id="kb_789"
    )
    if success:
        print("文件删除成功")
    else:
        print("文件不存在")
except ValueError as e:
    print(f"权限验证失败: {e}")
except Exception as e:
    print(f"数据库操作失败: {e}")
```

## 注意事项

1. **不可逆操作**：删除操作不可逆，请确保在调用前进行充分验证
2. **权限检查**：函数会严格验证用户权限，防止跨用户删除
3. **事务性**：所有操作在事务中执行，确保数据一致性
4. **触发器依赖**：依赖数据库触发器正确配置，请确保触发器已正确创建

## 测试建议

1. **参数验证测试**：测试空参数、无效参数的处理
2. **权限验证测试**：测试跨用户、跨知识库的访问控制
3. **数据一致性测试**：验证删除后相关表的数据状态
4. **事务回滚测试**：模拟异常情况下的事务回滚
