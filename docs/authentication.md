# Authentication & Authorization

Unifiles 使用 **API Key** 方式进行身份认证，确保只有授权用户可以访问 API 资源。

## 认证概述

### 认证流程

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth Service
    participant Database

    Client->>API: Request with API Key
    API->>Auth Service: Validate API Key
    Auth Service->>Database: Query key_hash
    Database-->>Auth Service: Return user info
    Auth Service-->>API: Authentication result
    API-->>Client: Response (200 OK or 401 Unauthorized)
```

## 获取 API Key

### 1. 注册用户

```bash
curl -X POST http://localhost:8088/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-username",
    "email": "your@email.com",
    "password": "your-secure-password"
  }'
```

响应：

```json
{
  "success": true,
  "data": {
    "user_id": "uuid-here",
    "username": "your-username",
    "api_key": "[REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "created_at": "2025-01-04T10:00:00Z"
  },
  "message": "User registered successfully"
}
```

**重要提示**：
- API Key 仅在注册时返回一次，请妥善保存
- 如果丢失，需要重新生成（旧的将失效）

### 2. 重新生成 API Key

如果 API Key 泄露或丢失，可以重新生成：

```bash
curl -X POST http://localhost:8088/api/v1/auth/regenerate-key \
  -H "Authorization: Bearer [REDACTED]"
```

响应：

```json
{
  "success": true,
  "data": {
    "api_key": "sk_live_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
    "created_at": "2025-01-04T11:00:00Z"
  },
  "message": "API key regenerated successfully"
}
```

## 使用 API Key

### HTTP Header 认证

所有 API 请求都需要在 HTTP Header 中包含 API Key：

```
Authorization: Bearer [REDACTED]
```

### 示例

#### cURL

```bash
curl http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer [REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

#### Python (requests)

```python
import requests

headers = {
    "Authorization": "Bearer [REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}

response = requests.get(
    "http://localhost:8088/api/v1/files",
    headers=headers
)
```

#### Python (unifiles-client SDK)

```python
from unifiles_client import UnifilesClient

client = UnifilesClient(api_key="[REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
files = client.files.list()
```

#### JavaScript (fetch)

```javascript
fetch('http://localhost:8088/api/v1/files', {
  headers: {
    'Authorization': 'Bearer [REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
  }
})
.then(response => response.json())
.then(data => console.log(data));
```

## API Key 格式

### 结构

```
sk_<environment>_<random_string>
```

- `sk`: Secret Key 前缀
- `<environment>`: 环境标识
  - `live`: 生产环境
  - `test`: 测试环境
- `<random_string>`: 32字符随机字符串（URL-safe Base64）

### 示例

```
[REDACTED]
[REDACTED]
```

## 安全最佳实践

### 1. 存储 API Key

**✅ 推荐做法**：

- 使用环境变量存储：
  ```bash
  export UNIFILES_API_KEY=[REDACTED]
  ```

- 使用配置文件（添加到 .gitignore）：
  ```python
  # config.py
  import os
  API_KEY = os.getenv('UNIFILES_API_KEY')
  ```

- 使用密钥管理服务：
  - AWS Secrets Manager
  - Azure Key Vault
  - HashiCorp Vault

**❌ 避免做法**：

- 直接硬编码在代码中
- 提交到版本控制系统
- 在日志中打印完整的 API Key

### 2. 定期轮换

建议每 90 天轮换一次 API Key：

```bash
# 1. 生成新的 API Key
curl -X POST http://localhost:8088/api/v1/auth/regenerate-key \
  -H "Authorization: Bearer OLD_KEY"

# 2. 更新应用中的 API Key

# 3. 测试新 Key 是否正常工作

# 4. 旧 Key 自动失效
```

### 3. 限制 API Key 权限

未来版本将支持细粒度权限控制：

```json
{
  "api_key": "[REDACTED]",
  "permissions": {
    "files": ["read", "write", "delete"],
    "knowledge_bases": ["read", "write"],
    "processors": ["read"]
  }
}
```

### 4. IP 白名单（计划中）

限制 API Key 只能从特定 IP 地址访问：

```json
{
  "api_key": "[REDACTED]",
  "allowed_ips": ["192.168.1.100", "10.0.0.0/24"]
}
```

## 错误处理

### 认证失败

**401 Unauthorized** - API Key 无效或缺失

```json
{
  "success": false,
  "data": null,
  "message": "Invalid or missing API key",
  "error": {
    "code": "UNAUTHORIZED",
    "details": "The API key provided is invalid or has expired"
  }
}
```

**解决方法**：
1. 检查 API Key 是否正确
2. 确认 `Authorization` Header 格式正确
3. 验证 API Key 是否已过期
4. 如果 Key 丢失，重新生成

### 权限不足

**403 Forbidden** - 没有访问权限

```json
{
  "success": false,
  "data": null,
  "message": "Insufficient permissions",
  "error": {
    "code": "FORBIDDEN",
    "details": "Your API key does not have permission to access this resource"
  }
}
```

## 速率限制

为了保护服务稳定性，API 实施速率限制：

| 端点类型 | 限制 | 时间窗口 |
|---------|------|---------|
| 文件上传 | 100 次 | 1 小时 |
| 内容提取 | 50 次 | 1 小时 |
| 知识库搜索 | 1000 次 | 1 小时 |
| 其他 API | 500 次 | 1 小时 |

### 速率限制响应

**429 Too Many Requests**

```json
{
  "success": false,
  "data": null,
  "message": "Rate limit exceeded",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "details": "You have exceeded the rate limit. Try again in 3600 seconds",
    "retry_after": 3600
  }
}
```

### 响应 Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1609459200
```

## 审计日志

所有 API 请求都会被记录，包括：

- 请求时间
- API Key（部分哈希）
- 请求路径和方法
- IP 地址
- 响应状态码
- 处理时长

查询审计日志：

```bash
curl http://localhost:8088/api/v1/auth/audit-logs \
  -H "Authorization: Bearer [REDACTED]" \
  -G \
  --data-urlencode "start_date=2025-01-01" \
  --data-urlencode "end_date=2025-01-31"
```

## 多租户隔离

Unifiles 实现了严格的多租户隔离：

- 每个 API Key 绑定到一个用户
- 用户只能访问自己的资源
- 数据库查询自动添加用户过滤条件

```sql
-- 自动注入的过滤条件
SELECT * FROM files WHERE user_id = 'current_user_id';
```

## OAuth 2.0 支持（计划中）

未来版本将支持 OAuth 2.0 认证流程：

- Authorization Code Flow
- Client Credentials Flow
- Device Authorization Flow

## JWT Token（内部使用）

虽然 API 使用 API Key 认证，但内部服务间通信使用 JWT Token：

```python
from unifiles.core.security.encryption import create_jwt_token, decode_jwt_token

# 创建 Token
token = create_jwt_token({
    "user_id": "uuid-here",
    "username": "john_doe",
    "exp": 3600  # 1 hour
})

# 验证 Token
payload = decode_jwt_token(token)
```

## 相关文档

- [API 参考](api-reference.md) - 完整的 API 端点文档
- [安全架构](../ARCHITECTURE.md) - 系统安全设计
- [快速开始](quickstart.md) - 开始使用 Unifiles

## 常见问题

**Q: API Key 是否会过期？**
A: 目前 API Key 不会自动过期，但建议定期轮换。

**Q: 可以同时使用多个 API Key 吗？**
A: 当前每个用户只能有一个有效的 API Key，生成新的会使旧的失效。

**Q: API Key 泄露了怎么办？**
A: 立即重新生成新的 API Key，旧的将自动失效。

**Q: 可以为不同的应用分配不同的 API Key 吗？**
A: 目前不支持，但计划在未来版本中添加此功能。

**Q: 如何撤销 API Key？**
A: 重新生成新的 API Key 会自动撤销旧的。
