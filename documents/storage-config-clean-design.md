# StorageConfig 干净架构设计文档 - 第一版系统

## 🎯 设计目标

创建一个类型安全、无历史包袱的存储配置系统，适用于第一版开发。

### 核心原则
- **类型安全**: 每个存储提供商有独立的连接类
- **环境驱动**: 使用环境变量指定默认存储
- **JSONB存储**: 数据库用JSON格式存储连接配置  
- **无兼容性**: 不支持任何遗留格式

---

## 🏗️ 架构设计

### 连接模型层次结构

```python
BaseConnection (Abstract)
├── LocalConnection      # provider: "local" 
├── MinIOConnection      # provider: "minio"
├── S3Connection         # provider: "s3"
├── AzureConnection      # provider: "azure"
└── GCSConnection        # provider: "gcs"
```

### StorageConfig 模型

```python
@dataclass
class StorageConfig:
    id: str                           # 配置唯一ID
    name: str                         # 显示名称
    connection: ConnectionConfig      # 连接配置
    is_active: bool = True            # 是否启用
    config_source: ConfigSource = ConfigSource.MANUAL
    public_url_prefix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

### 数据库Schema

```sql
CREATE TABLE unifiles.storage_configs (
    id TEXT PRIMARY KEY,
    storage_name TEXT NOT NULL,
    connection_config JSONB NOT NULL,        -- JSON存储连接配置
    is_active BOOLEAN DEFAULT TRUE,
    config_source TEXT DEFAULT 'manual',
    public_url_prefix TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- 检查约束
    CONSTRAINT chk_storage_configs_connection_has_provider
        CHECK (connection_config ? 'provider')
);
```

---

## 🔧 实现细节

### 1. 连接配置示例

**MinIO配置：**
```json
{
  "provider": "minio",
  "endpoint": "localhost:9000", 
  "access_key": "minioadmin",
  "secret_key": "minioadmin",
  "bucket_name": "unifiles",
  "region": "us-east-1",
  "secure": false
}
```

**本地存储配置：**
```json
{
  "provider": "local",
  "base_path": "/uploads",
  "create_if_missing": true
}
```

### 2. 环境变量配置

```env
# 必需：指定默认存储ID
UNIFILES_STORAGE_DEFAULT_ID=default-local

# 可选：fallback策略
UNIFILES_STORAGE_DEFAULT_FALLBACK=fail_fast  # 或 use_first_active

# MinIO配置（可选）
UNIFILES_STORAGE_MINIO_ADDRESS=localhost:9000
UNIFILES_STORAGE_MINIO_ACCESS_KEY=minioadmin
UNIFILES_STORAGE_MINIO_SECRET_KEY=minioadmin
UNIFILES_STORAGE_MINIO_BUCKET_NAME=unifiles
```

### 3. 工厂模式

```python
class StorageFactory:
    @classmethod
    def create_storage(cls, config: StorageConfig) -> StorageBackend:
        """只接受StorageConfig对象，不支持字典格式"""
        if not isinstance(config, StorageConfig):
            raise ValueError("Only StorageConfig objects supported")
        
        provider_type = config.connection.provider
        storage_class = cls._backends[provider_type]
        return storage_class(config)
```

---

## 📝 使用方式

### 创建配置

```python
# 创建MinIO连接
connection = MinIOConnection(
    endpoint="localhost:9000",
    access_key="admin",
    secret_key="admin123",
    bucket_name="my-bucket"
)

# 创建存储配置
config = StorageConfig(
    id="production-minio",
    name="生产MinIO存储",
    connection=connection,
    public_url_prefix="https://cdn.example.com"
)

# 验证配置
config.validate()  # 自动调用连接验证
```

### 从字典创建

```python
config_data = {
    'id': 'my-storage',
    'name': 'My Storage',
    'connection': {
        'provider': 'minio',
        'endpoint': 'localhost:9000',
        'access_key': 'admin',
        'secret_key': 'admin123',
        'bucket_name': 'test'
    }
}

config = StorageConfig.from_dict(config_data)
```

### 创建存储后端

```python
# 通过工厂创建
backend = StorageFactory.create_storage(config)

# 使用存储
await backend.upload_file("path/file.txt", content)
```

---

## ✅ 验证检查

### 类型安全
- [ ] 每个提供商有独立的连接类
- [ ] 连接创建时进行类型验证
- [ ] 工厂模式严格类型检查

### 环境配置
- [ ] `UNIFILES_STORAGE_DEFAULT_ID` 正确工作
- [ ] Fallback策略按预期执行
- [ ] 环境配置同步正常

### 数据库
- [ ] JSONB存储和查询正常
- [ ] 约束检查生效
- [ ] 索引优化JSONB查询

### 测试覆盖
- [ ] 所有连接模型测试通过
- [ ] 存储配置创建和验证测试
- [ ] 工厂模式和错误处理测试
- [ ] 数据库集成测试

---

## 🚀 部署步骤

1. **环境变量设置**
   ```bash
   # 设置默认存储
   export UNIFILES_STORAGE_DEFAULT_ID="default-local"
   ```

2. **数据库初始化**
   ```bash
   # 运行建表脚本
   psql -f scripts/sql/031-create-file-management.sql
   ```

3. **应用启动**
   ```bash
   # 启动应用，存储系统自动初始化
   python -m unifiles.app.main
   ```

4. **验证配置**
   ```bash
   # 检查存储健康状态
   curl http://localhost:8000/api/storage/health
   ```

---