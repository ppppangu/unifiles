# 文件删除模块完整文档

## 概述

`delete_file_module.py` 提供了完整的文件删除功能，包括从向量数据库和MinIO对象存储中删除文件及其相关数据。该模块包含两个主要函数：

1. `delete_file_from_vcdb` - 从向量数据库删除文件数据
2. `delete_file_from_minio` - 从MinIO对象存储删除文件

## 模块架构

### 数据存储架构
```
┌─────────────────┐    ┌─────────────────┐
│   向量数据库     │    │   MinIO存储     │
│   (PostgreSQL)  │    │   (对象存储)    │
└─────────────────┘    └─────────────────┘
         │                       │
         │                       │
    ┌────▼────┐              ┌───▼───┐
    │ 元数据   │              │ 文件  │
    │ 文本块   │              │ 图片  │
    │ 向量     │              │ 文档  │
    └─────────┘              └───────┘
```

### 删除流程
```
用户请求删除文件
        │
        ▼
┌───────────────┐
│ 参数验证      │
│ 权限检查      │
└───────┬───────┘
        │
        ▼
┌───────────────┐    ┌───────────────┐
│ 删除数据库数据 │    │ 删除MinIO文件 │
│ (vcdb)        │    │ (minio)       │
└───────────────┘    └───────────────┘
        │                    │
        ▼                    ▼
┌───────────────┐    ┌───────────────┐
│ 触发器级联删除 │    │ 递归删除目录  │
│ 更新索引数组  │    │ 清理相关文件  │
└───────────────┘    └───────────────┘
```

## 函数详解

### 1. delete_file_from_vcdb

#### 功能描述
从向量数据库中删除文件及其所有相关数据，利用数据库触发器实现级联删除。

#### 核心特性
- **权限验证**：双重验证确保用户只能删除自己的文件
- **事务安全**：所有操作在单个事务中执行
- **触发器自动化**：利用数据库触发器处理级联删除
- **详细日志**：记录删除过程和结果

#### 删除机制
```sql
-- 只需删除documents表记录
DELETE FROM chunk_schema.documents 
WHERE id = $1 AND knowledge_base_id = $2

-- 触发器自动处理：
-- 1. 级联删除 components, chunks, photos
-- 2. 更新 knowledge_bases.document_ids 数组
```

#### 使用示例
```python
try:
    success = await delete_file_from_vcdb(
        user_id="user_123",
        file_id="doc_456",
        knowledge_base_id="kb_789"
    )
    if success:
        print("数据库删除成功")
except ValueError as e:
    print(f"权限验证失败: {e}")
```

### 2. delete_file_from_minio

#### 功能描述
从MinIO对象存储中删除文件及其相关文件，支持多路径查找和删除。

#### 存储路径结构
```
bucket_name/
├── {user_id}/
│   ├── knowledgebase/
│   │   └── {knowledge_base_id}/
│   │       └── {file_id}/
│   │           ├── {file_id}.pdf
│   │           ├── {file_id}.md
│   │           └── {file_id}.json
│   └── default_file_space/
│       └── {file_id}/
│           └── {filename}
```

#### 删除策略
1. **主要路径优先**：`{user_id}/knowledgebase/{knowledge_base_id}/{file_id}/`
2. **默认路径回退**：`{user_id}/default_file_space/{file_id}/`
3. **递归删除**：删除目录下所有文件
4. **错误容忍**：单个文件删除失败不影响其他文件

#### 使用示例
```python
try:
    success = await delete_file_from_minio(
        user_id="user_123",
        file_id="doc_456",
        knowledge_base_id="kb_789"
    )
    if success:
        print("MinIO删除成功")
except Exception as e:
    print(f"MinIO操作失败: {e}")
```

## 配置要求

### config.yaml 配置
```yaml
server_components:
  pg_vector:
    host: "192.168.132.149"
    port: "5437"
    user: "postgres"
    password: "postgres"
    database: "postgres"
    active: true
  minio:
    host: "192.168.132.149"
    port: 9000
    access_key: "[REDACTED]"
    secret_key: "[REDACTED]"
    bucket_name: "publicfiles"
    region: "us-east-1"
    use_public_url: true
    public_url_prefix: "http://1.tcp.cpolar.cn:21729"
    active: true
```

## 错误处理

### 常见错误类型
1. **参数验证错误** (`ValueError`)
   - 空参数
   - 无效格式

2. **权限验证错误** (`ValueError`)
   - 知识库不属于用户
   - 文档不属于知识库

3. **数据库错误** (`Exception`)
   - 连接失败
   - 外键约束冲突
   - PostgreSQL错误

4. **MinIO错误** (`Exception`)
   - 连接失败
   - 桶不存在
   - 文件删除失败

### 错误处理示例
```python
try:
    await delete_file_from_vcdb(user_id, file_id, kb_id)
    await delete_file_from_minio(user_id, file_id, kb_id)
except ValueError as e:
    logger.error(f"验证失败: {e}")
    return {"error": "权限不足或参数无效"}
except Exception as e:
    logger.error(f"操作失败: {e}")
    return {"error": "系统错误"}
```

## 测试

### 测试文件
- `test_delete_file_from_vcdb.py` - 数据库删除测试
- `test_delete_file_from_minio.py` - MinIO删除测试

### 测试覆盖
1. **参数验证测试**
2. **权限验证测试**
3. **连接测试**
4. **路径测试**
5. **错误处理测试**

### 运行测试
```bash
python test_delete_file_from_vcdb.py
python test_delete_file_from_minio.py
```

## 最佳实践

### 1. 调用顺序
建议先删除数据库数据，再删除MinIO文件：
```python
# 先删除数据库数据（包含业务逻辑验证）
await delete_file_from_vcdb(user_id, file_id, knowledge_base_id)
# 再删除MinIO文件（物理文件清理）
await delete_file_from_minio(user_id, file_id, knowledge_base_id)
```

### 2. 错误恢复
如果MinIO删除失败，数据库数据已删除，可以：
- 记录孤立文件日志
- 定期清理孤立文件
- 提供手动清理接口

### 3. 日志记录
- 使用loguru记录详细操作日志
- 区分不同级别的日志（info, warning, error）
- 记录关键参数和操作结果

### 4. 性能优化
- 使用事务确保数据一致性
- 批量删除MinIO文件
- 异步操作提高响应速度

## 依赖项

- `asyncpg` - PostgreSQL异步客户端
- `minio` - MinIO Python SDK
- `loguru` - 日志记录
- `yaml` - 配置文件解析
- `pathlib` - 路径处理

## 注意事项

1. **不可逆操作**：删除操作不可逆，请谨慎使用
2. **权限控制**：严格的权限验证防止误删
3. **事务性**：数据库操作具有事务性
4. **错误容忍**：MinIO删除具有一定的错误容忍性
5. **日志审计**：详细的日志便于问题排查和审计
