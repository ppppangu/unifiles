# save_text_to_vcdb_text_table 函数文档

## 概述

`save_text_to_vcdb_text_table` 是一个基础函数，用于将文本段保存到 `chunk_schema.chunks` 表中。该函数遵循数据库架构设计，通过触发器自动同步到 `chunk_schema.components` 表，并处理所有相关的数据更新。

## 数据库架构理解

### 表结构层次
```
Users (用户)
  ↓ 1:N
Knowledge Bases (知识库)
  ↓ 1:N  
Documents (文档)
  ↓ 1:N
Components (组件) ← 目标表
  ↓ 1:1
Chunks/Photos (文本块/图片)
```

### 核心表：chunk_schema.chunks
```sql
CREATE TABLE chunk_schema.chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    text TEXT,
    embedding vector,           -- 文本的向量嵌入
    doc_position INTEGER
);
```

### 触发器自动同步到：chunk_schema.components
```sql
CREATE TABLE chunk_schema.components (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    doc_position INTEGER NOT NULL,
    type TEXT CHECK (type IN ('chunk','photo','table')),
    text TEXT,
    embedding vector,           -- 文本的向量嵌入
    tsv tsvector,              -- 文本的倒排索引
    UNIQUE (document_id, doc_position)
);
```

## 函数签名

```python
async def save_text_to_vcdb_text_table(
    text: str,
    document_id: str,
    user_id: str,
    knowledge_base_id: str,
    chunk_id: Optional[str] = None,
    doc_position: Optional[int] = None,
    embedding: Optional[List[float]] = None
) -> str:
```

## 参数说明

| 参数                | 类型                  | 必需 | 说明                           |
| ------------------- | --------------------- | ---- | ------------------------------ |
| `text`              | str                   | ✅    | 文本内容，不能为空             |
| `document_id`       | str                   | ✅    | 文档ID，外键引用               |
| `user_id`           | str                   | ✅    | 用户ID，用于验证权限           |
| `knowledge_base_id` | str                   | ✅    | 知识库ID，用于验证权限         |
| `chunk_id`          | Optional[str]         | ❌    | 文本块ID，默认自动生成UUID     |
| `doc_position`      | Optional[int]         | ❌    | 文档位置，默认由触发器自动分配 |
| `embedding`         | Optional[List[float]] | ❌    | 向量嵌入，可后续更新           |

## 返回值

- **类型**: `str`
- **内容**: 插入的文本块ID

## 功能特性

### 1. 自动触发器集成
函数插入数据后，以下触发器会自动执行：

- **位置唯一性**: `ensure_doc_position_uniqueness()` 确保 `doc_position` 唯一
- **全文搜索**: `update_component_tsv()` 自动更新 `tsv` 字段
- **文档内容**: `update_document_content()` 更新文档的完整文本
- **关联更新**: `update_component_document_ids()` 更新文档的组件ID数组

### 2. 数据验证
- 验证文本内容非空
- 验证必需参数存在
- 验证组件类型有效性
- 验证文档存在性和权限

### 3. 错误处理
- 参数验证错误 → `ValueError`
- 唯一约束冲突 → `ValueError`
- 外键约束冲突 → `ValueError`
- 其他数据库错误 → `Exception`

## 使用示例

### 基本用法
```python
component_id = await save_text_to_vcdb_text_table(
    text="这是一段测试文本",
    document_id="doc_123",
    user_id="user_456", 
    knowledge_base_id="kb_789"
)
```

### 完整参数用法
```python
component_id = await save_text_to_vcdb_text_table(
    text="这是一段测试文本",
    document_id="doc_123",
    user_id="user_456",
    knowledge_base_id="kb_789",
    component_id="custom_comp_id",
    doc_position=5,
    embedding=[0.1, 0.2, 0.3, ...],
    component_type="chunk"
)
```

### 不同组件类型
```python
# 文本块
await save_text_to_vcdb_text_table(..., component_type="chunk")

# 图片描述
await save_text_to_vcdb_text_table(..., component_type="photo")

# 表格内容
await save_text_to_vcdb_text_table(..., component_type="table")
```

## 数据库连接配置

函数使用 `config.yaml` 中的数据库配置：

```yaml
server_components:
  pg_vector:
    host: "192.168.132.149"
    port: "5437"
    user: "postgres"
    password: "postgres"
    database: "postgres"
    active: true
```

## 日志记录

函数使用 `loguru` 记录以下信息：
- 成功插入的详细信息
- 错误和异常信息
- 数据库操作状态

## 依赖项

- `asyncpg`: PostgreSQL异步连接
- `loguru`: 日志记录
- `uuid`: ID生成
- `typing`: 类型注解

## 注意事项

1. **事务安全**: 所有数据库操作都在事务中执行
2. **连接管理**: 自动管理数据库连接的打开和关闭
3. **触发器依赖**: 依赖数据库触发器正确配置
4. **权限验证**: 验证用户对文档的访问权限
5. **位置管理**: `doc_position` 由触发器自动管理，确保唯一性

## 错误处理示例

```python
try:
    component_id = await save_text_to_vcdb_text_table(
        text="测试文本",
        document_id="invalid_doc",
        user_id="user_123",
        knowledge_base_id="kb_456"
    )
except ValueError as e:
    print(f"参数错误: {e}")
except Exception as e:
    print(f"数据库错误: {e}")
```

## 测试

使用 `test_save_text_to_vcdb.py` 进行功能测试：

```bash
python test_save_text_to_vcdb.py
```

测试覆盖：
- 基本功能测试
- 参数验证测试
- 自定义参数测试
- 不同组件类型测试
- 错误处理测试
