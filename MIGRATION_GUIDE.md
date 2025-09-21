# 文件上传系统安全重构迁移指南

## 概述

本文档指导如何从当前的文件上传系统迁移到新的安全增强架构。新架构提供了更好的安全性、性能和可维护性。

## 新架构特性

### 🔒 安全增强
- **文件内容验证**：魔数检测防止文件类型伪造
- **输入清理**：防止路径遍历和注入攻击
- **权限验证**：一致的文件所有权检查
- **审计日志**：完整的操作记录
- **连接池**：安全的数据库连接管理

### 🏗️ 架构改进
- **服务层分离**：业务逻辑从路由器中分离
- **存储抽象**：支持多种存储后端
- **依赖注入**：更好的测试和维护性
- **错误处理**：统一的异常处理机制

### 📊 性能优化
- **连接池**：数据库连接复用
- **预签名URL**：减少服务器负载
- **指标收集**：性能监控和分析

## 迁移步骤

### 第一步：更新数据库架构

#### 1.1 添加新字段到现有表
```sql
-- 为文件表添加安全字段
ALTER TABLE unifiles.files 
ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS storage_config_id VARCHAR(100) DEFAULT 'minio-default',
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

-- 为用户表添加创建时间
ALTER TABLE unifiles.users 
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- 创建访问令牌表（如果不存在）
CREATE TABLE IF NOT EXISTS unifiles.access_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    description TEXT,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES unifiles.users(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_files_user_status ON unifiles.files(user_id, status);
CREATE INDEX IF NOT EXISTS idx_files_public ON unifiles.files(is_public) WHERE is_public = TRUE;
CREATE INDEX IF NOT EXISTS idx_access_tokens_active ON unifiles.access_tokens(token) WHERE is_active = TRUE;
```

#### 1.2 数据迁移脚本
```sql
-- 更新现有文件的storage_config_id
UPDATE unifiles.files 
SET storage_config_id = 'minio-default' 
WHERE storage_config_id IS NULL;

-- 为现有用户添加创建时间
UPDATE unifiles.users 
SET created_at = NOW() 
WHERE created_at IS NULL;
```

### 第二步：部署新代码

#### 2.1 安装新依赖
```bash
# 如果需要添加新的Python包
pip install -r requirements.txt
```

#### 2.2 更新配置文件
确保配置文件包含所有必需的参数：

```yaml
# config.yaml 示例
storage:
  type: minio
  host: localhost
  port: 9000
  access_key: your_access_key
  secret_key: your_secret_key
  bucket_name: unifiles
  secure: false
  
database:
  host: localhost
  port: 5432
  database: your_db
  user: your_user
  password: your_password
  
security:
  max_file_size: 104857600  # 100MB
  allowed_extensions: ['.pdf', '.doc', '.docx', '.jpg', '.png']
  enable_audit_log: true
```

### 第三步：切换到安全路由器

#### 3.1 更新路由注册

```python
# 在主应用中替换路由器
from unifiles.app.routers.unifiles_secure import router as secure_files_router

# 替换原有的路由器
app.include_router(secure_files_router, prefix="/api/v1")
```

#### 3.2 更新中间件配置
确保认证中间件正确配置：

```python
from unifiles.core.services import AuthService

# 在中间件中使用新的AuthService
async def auth_middleware(request: Request, call_next):
    auth_service = AuthService(pg_config)
    # ... 认证逻辑
```

### 第四步：测试验证

#### 4.1 基础功能测试
```bash
# 运行测试脚本
python test_migration.py
```

#### 4.2 安全测试清单
- [ ] 文件上传时的类型验证
- [ ] 路径遍历攻击防护
- [ ] 文件所有权验证
- [ ] 公共/私有文件访问控制
- [ ] 数据库注入防护
- [ ] 审计日志记录

#### 4.3 性能测试
- [ ] 并发上传测试
- [ ] 大文件上传测试
- [ ] 数据库连接池效果
- [ ] 内存使用情况

## 兼容性说明

### API 兼容性
新的安全路由器与原有API完全兼容，客户端无需修改。

### 数据库兼容性
新架构向后兼容现有数据，但建议运行迁移脚本以获得最佳性能。

### 配置兼容性
原有的配置文件仍然有效，但建议添加新的安全配置项。

## 回滚计划

如果需要回滚到原有系统：

1. **停止新服务**
2. **恢复原有路由器配置**
3. **如果修改了数据库架构，运行回滚脚本**：

```sql
-- 回滚脚本示例（谨慎使用）
ALTER TABLE unifiles.files 
DROP COLUMN IF EXISTS is_public,
DROP COLUMN IF EXISTS storage_config_id,
DROP COLUMN IF EXISTS updated_at,
DROP COLUMN IF EXISTS deleted_at;

DROP TABLE IF EXISTS unifiles.access_tokens;
```

## 监控和维护

### 监控指标
- 文件上传成功率
- 平均响应时间
- 安全事件数量
- 存储使用量
- 数据库连接池状态

### 日志分析
```bash
# 查看安全相关日志
grep "SECURITY" application.log

# 查看审计日志
grep "DB_AUDIT" application.log

# 查看性能指标
grep "API Response" application.log | awk '{print $NF}' | sort -n
```

### 定期维护任务
```python
# 清理过期令牌
await auth_service.cleanup_expired_tokens()

# 清理已删除文件
await secure_file_db_manager.cleanup_deleted_files(days_old=30)

# 检查存储健康状态
health = await file_service.get_storage_health()
```

## 故障排除

### 常见问题

#### 1. 文件上传失败
**症状**：上传返回400错误
**解决**：检查文件类型验证和大小限制
```python
# 检查验证结果
validation_result = FileSecurityValidator.validate_upload_file(content, filename)
print(validation_result)
```

#### 2. 数据库连接问题
**症状**：连接池错误
**解决**：检查数据库配置和连接数限制
```python
# 初始化连接池
await secure_file_db_manager.init_connection_pool(min_size=5, max_size=20)
```

#### 3. 权限验证失败
**症状**：403 Forbidden错误
**解决**：检查token和文件所有权
```python
# 验证token
valid, user_info = await auth_service.validate_token(token, client_ip)
```

### 性能调优

#### 数据库优化
```sql
-- 检查查询性能
EXPLAIN ANALYZE SELECT * FROM unifiles.files WHERE user_id = 'user123';

-- 添加缺失的索引
CREATE INDEX IF NOT EXISTS idx_files_created_at ON unifiles.files(created_at DESC);
```

#### 存储优化
```python
# 调整MinIO参数
storage_config = {
    'part_size': 10 * 1024 * 1024,  # 10MB
    'connection_timeout': 30,
    'read_timeout': 60
}
```

## 支持联系

如遇到问题，请提供以下信息：
- 错误日志
- 配置文件（隐藏敏感信息）
- 复现步骤
- 环境信息

迁移完成后，系统将具备企业级的安全性和可扩展性，为后续的功能扩展打下坚实基础。