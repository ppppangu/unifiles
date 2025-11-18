# 用户和访问密钥管理 API

本文档提供用户创建和访问密钥（Access Key）管理的API端点说明，适用于首次部署和日常用户管理场景。

## 概述

访问密钥（Access Key）是系统的主要认证方式，采用Bearer Token格式。典型流程：

1. **创建用户** (`POST /users/create`) - 无需认证
2. **创建访问密钥** (`POST /users/{user_id}/access-keys`) - 无需认证
3. **使用访问密钥** - 在后续所有API请求的`Authorization`头中使用

---

## 用户管理

### 1. 创建用户

**POST** `/users/create`

创建新用户账户。此端点不需要认证，用于系统初始化或自助注册场景。

**请求体:**
```json
{
  "user_id": "user_001",
  "username": "john_doe",
  "email": "john@example.com",
  "display_name": "John Doe",
  "user_settings": {}
}
```

**字段说明:**
- `user_id` (string, required): 用户唯一标识，1-128字符
- `username` (string, optional): 用户名，最多128字符
- `email` (string, optional): 邮箱地址，最多256字符
- `display_name` (string, optional): 显示名称，最多128字符
- `user_settings` (object, optional): 用户配置JSON对象

**请求示例:**
```bash
curl -X POST "http://localhost:8088/users/create" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe"
  }'
```

**响应示例 (成功):**
```json
{
  "success": true,
  "message": "User created successfully",
  "user": {
    "id": "user_001",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2024-10-16T10:30:00.123456",
    "updated_at": null,
    "last_login_at": null
  }
}
```

**错误响应 (用户已存在):**
```json
{
  "detail": "User with ID 'user_001' already exists"
}
```
HTTP状态码: `409 Conflict`

---

### 2. 获取用户信息

**GET** `/users/{user_id}`

获取指定用户的详细信息。此端点不需要认证。

**请求示例:**
```bash
curl -X GET "http://localhost:8088/users/user_001"
```

**响应示例:**
```json
{
  "success": true,
  "message": "User retrieved successfully",
  "data": {
    "id": "user_001",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2024-10-16T10:30:00.123456",
    "updated_at": null,
    "last_login_at": null
  }
}
```

---

### 3. 用户登录（通过邮箱）

**POST** `/users/login?email={email}`

通过邮箱查询用户信息，用于登录场景。此端点不需要认证。

**查询参数:**
- `email` (string, required): 用户邮箱

**请求示例:**
```bash
curl -X POST "http://localhost:8088/users/login?email=john@example.com"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "id": "user_001",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "user_status": "active",
    "user_role": "user",
    "knowledge_ids": [],
    "user_settings": {},
    "created_at": "2024-10-16T10:30:00.123456",
    "updated_at": null,
    "last_login_at": null
  }
}
```

---

## 访问密钥管理

### 1. 创建访问密钥

**POST** `/users/{user_id}/access-keys`

为指定用户创建访问密钥（API Key）。此端点不需要认证，用于引导首个密钥的创建。

**路径参数:**
- `user_id` (string, required): 用户ID

**请求体:**
```json
{
  "name": "Production API Key",
  "description": "用于生产环境的API密钥",
  "scopes": ["read", "write"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**字段说明:**
- `name` (string, required): 密钥名称，1-128字符
- `description` (string, optional): 密钥描述
- `scopes` (array, optional): 权限范围，默认`["read", "write"]`
- `expires_at` (string, optional): 过期时间（RFC3339格式），默认永不过期

**请求示例:**
```bash
curl -X POST "http://localhost:8088/users/user_001/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Key",
    "description": "用于测试的密钥",
    "scopes": ["read", "write"]
  }'
```

**响应示例 (成功):**
```json
{
  "success": true,
  "message": "Access key created successfully",
  "key_id": "ak_3f8a9b2c1d4e5f6a7b8c9d0e1f2a3b4c",
  "access_key": "[REDACTED]"
}
```

**重要提示:**
- `access_key`字段包含完整的Bearer Token，**只在创建时返回一次**
- 立即保存此密钥，后续无法再次查看
- 在后续API请求中使用格式：`Authorization: Bearer sk_9876543...`

**错误响应:**
```json
{
  "detail": "User 'user_001' not found"
}
```
HTTP状态码: `404 Not Found`

---

### 2. 获取访问密钥列表

**GET** `/users/{user_id}/access-keys`

获取指定用户的所有访问密钥列表（不包含完整密钥值）。此端点不需要认证。

**路径参数:**
- `user_id` (string, required): 用户ID

**查询参数 (可选):**
- `active` (boolean, optional): 过滤条件
  - `true`: 仅返回活跃的密钥
  - `false`: 仅返回已禁用的密钥
  - 不传: 返回所有密钥

**请求示例:**
```bash
# 获取所有密钥
curl -X GET "http://localhost:8088/users/user_001/access-keys"

# 仅获取活跃密钥
curl -X GET "http://localhost:8088/users/user_001/access-keys?active=true"
```

**响应示例:**
```json
{
  "success": true,
  "message": "Access keys retrieved successfully",
  "access_keys": [
    {
      "id": "ak_3f8a9b2c1d4e5f6a7b8c9d0e1f2a3b4c",
      "name": "My First Key",
      "description": "用于测试的密钥",
      "scopes": ["read", "write"],
      "is_active": true,
      "created_at": "2024-10-16T10:35:00.123456",
      "expires_at": "2025-12-31T23:59:59Z",
      "last_used_at": "2024-10-16T12:00:00.123456"
    },
    {
      "id": "ak_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
      "name": "Development Key",
      "description": null,
      "scopes": ["read"],
      "is_active": true,
      "created_at": "2024-10-16T11:00:00.123456",
      "expires_at": null,
      "last_used_at": null
    }
  ]
}
```

**字段说明:**
- `id`: 密钥ID（用于删除操作）
- `name`: 密钥名称
- `description`: 密钥描述
- `scopes`: 权限范围
- `is_active`: 是否启用
- `created_at`: 创建时间
- `expires_at`: 过期时间（`null`表示永不过期）
- `last_used_at`: 最后使用时间（`null`表示从未使用）

---

### 3. 删除访问密钥

**DELETE** `/users/{user_id}/access-keys/{key_id}`

删除（撤销）指定的访问密钥。此端点不需要认证。

**路径参数:**
- `user_id` (string, required): 用户ID
- `key_id` (string, required): 密钥ID（从列表接口获取）

**请求示例:**
```bash
curl -X DELETE "http://localhost:8088/users/user_001/access-keys/ak_3f8a9b2c1d4e5f6a7b8c9d0e1f2a3b4c"
```

**响应示例 (成功):**
```json
{
  "success": true,
  "message": "Access key deleted successfully",
  "data": {
    "key_id": "ak_3f8a9b2c1d4e5f6a7b8c9d0e1f2a3b4c"
  }
}
```

**错误响应 (密钥不属于该用户):**
```json
{
  "detail": "Access key 'ak_xxx' does not belong to user 'user_001'"
}
```
HTTP状态码: `403 Forbidden`

---

## 使用访问密钥

创建访问密钥后，在所有需要认证的API请求中添加Authorization头：

```bash
curl -X GET "http://localhost:8088/files" \
  -H "Authorization: Bearer [REDACTED]"
```

### 认证流程

1. `AuthMiddleware`从请求头提取`Bearer <token>`
2. 调用数据库函数`validate_access_key_simple(token)`验证
3. 验证成功返回`user_id`，失败返回`401 Unauthorized`
4. `user_id`存入`request.state`供后续使用

### 公开端点（无需认证）

以下端点不需要Bearer Token：
- `/health` - 健康检查
- `/docs`, `/redoc`, `/openapi.json` - API文档
- `/users/create` - 创建用户
- `/users/{user_id}` - 获取用户信息
- `/users/login` - 用户登录
- `/users/{user_id}/access-keys` - 所有访问密钥管理端点（创建、列表、删除）

---

## 快速开始示例

### 1. 初始化系统（创建首个用户和密钥）

```bash
# 步骤1: 创建用户
curl -X POST "http://localhost:8088/users/create" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "admin_001",
    "username": "admin",
    "email": "admin@example.com",
    "display_name": "System Admin"
  }'

# 步骤2: 创建访问密钥
curl -X POST "http://localhost:8088/users/admin_001/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Admin Master Key",
    "description": "主管理密钥"
  }'

# 响应示例:
# {
#   "success": true,
#   "message": "Access key created successfully",
#   "key_id": "ak_...",
#   "access_key": "[REDACTED]"  <-- 保存此密钥
# }

# 步骤3: 使用密钥访问其他API
export API_KEY="[REDACTED]"
curl -X GET "http://localhost:8088/files" \
  -H "Authorization: Bearer $API_KEY"
```

### 2. 管理多个密钥

```bash
# 为同一用户创建多个密钥（不同权限范围）
export USER_ID="admin_001"

# 只读密钥
curl -X POST "http://localhost:8088/users/$USER_ID/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Read Only Key",
    "scopes": ["read"]
  }'

# 有时效密钥
curl -X POST "http://localhost:8088/users/$USER_ID/access-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Temporary Key",
    "expires_at": "2024-12-31T23:59:59Z"
  }'

# 查看所有密钥
curl -X GET "http://localhost:8088/users/$USER_ID/access-keys"

# 删除某个密钥
curl -X DELETE "http://localhost:8088/users/$USER_ID/access-keys/ak_..."
```

---

## 数据库函数参考

系统使用PostgreSQL函数进行访问密钥管理：

### `create_access_key()`
位置: `scripts/sql/022-create-access-key-management.sql`

**函数签名:**
```sql
create_access_key(
    p_user_id TEXT,
    p_name TEXT,
    p_description TEXT DEFAULT NULL,
    p_scopes TEXT[] DEFAULT '{"read", "write"}'::TEXT[],
    p_expires_at TIMESTAMPTZ DEFAULT NULL,
    p_max_requests_per_hour INTEGER DEFAULT 1000,
    p_max_requests_per_day INTEGER DEFAULT 10000,
    p_max_file_size_mb INTEGER DEFAULT 100,
    p_max_knowledge_bases INTEGER DEFAULT 10,
    p_can_create_kb BOOLEAN DEFAULT TRUE,
    p_can_delete_files BOOLEAN DEFAULT TRUE,
    p_can_share_files BOOLEAN DEFAULT TRUE,
    p_can_export_data BOOLEAN DEFAULT TRUE,
    p_allowed_ips TEXT[] DEFAULT NULL
) RETURNS JSONB
```

**功能:** 生成并存储新的访问密钥，返回密钥ID和完整密钥值。

### `revoke_access_key()`
位置: `scripts/sql/022-create-access-key-management.sql`

**函数签名:**
```sql
revoke_access_key(p_key_id TEXT) RETURNS JSONB
```

**功能:** 软删除访问密钥（设置`is_active = FALSE`）。

### `validate_access_key_simple()`
位置: `scripts/sql/022-create-access-key-management.sql`

**函数签名:**
```sql
validate_access_key_simple(token TEXT) RETURNS TEXT
```

**功能:** 验证Bearer Token，成功返回`user_id`，失败返回`NULL`。

---

## 代码位置参考

- **路由定义**: `unifiles/app/routers/users.py`
  - 创建用户: 第30-115行
  - 创建访问密钥: 第267-334行
  - 获取密钥列表: 第336-396行
  - 删除访问密钥: 第398-474行

- **请求/响应模型**: `unifiles/app/schemas.py`
  - `UserCreateRequest`: 第175-183行
  - `AccessKeyCreateRequest`: 第210-221行
  - `AccessKeyCreateResponse`: 第223-230行
  - `AccessKeyInfo`: 第232-243行

- **数据库模型**: `unifiles/core/database/models.py`
  - `UserModel`: 第80-97行
  - `AccessKeyModel`: 第101-116行

- **用户管理器**: `unifiles/core/database/user_manager.py`
  - `create_user()`: 第18-56行
  - `get_user()`: 第58-84行

- **认证中间件**: `unifiles/app/middlewares.py`
  - `AuthMiddleware`: 第239-373行
  - Token验证: 第340-365行

- **数据库SQL函数**: `scripts/sql/022-create-access-key-management.sql`

---

## 错误处理

| HTTP状态码 | 场景 | 示例 |
|-----------|------|------|
| 200 | 成功 | 操作成功完成 |
| 400 | 请求参数错误 | 缺少必填字段、格式不正确 |
| 401 | 认证失败 | Bearer Token无效或过期 |
| 403 | 权限不足 | 尝试删除不属于自己的密钥 |
| 404 | 资源不存在 | 用户或密钥不存在 |
| 409 | 资源冲突 | 用户ID已存在 |
| 500 | 服务器内部错误 | 数据库连接失败等 |

---

## 安全注意事项

1. **密钥保管**: 访问密钥只在创建时返回一次，务必安全保存
2. **密钥轮换**: 定期创建新密钥并删除旧密钥
3. **最小权限原则**: 根据用途设置合适的`scopes`权限
4. **过期时间**: 对临时访问场景设置`expires_at`
5. **监控使用**: 通过`last_used_at`字段监控密钥使用情况
6. **立即撤销**: 密钥泄露时立即调用删除接口

---

## 相关文档

- [API完整参考](../API_REFERENCE.md)
- [文件上传工作流程](FILE_UPLOAD_WORKFLOW_CN.md)
- [系统架构设计](../ARCHITECTURE.md)
- [快速开始指南](../QUICK_START.md)
