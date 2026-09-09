# 安全模型

本文档详细介绍 Unifiles 的安全架构，包括认证、授权、加密和数据保护策略。

## 安全架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端请求                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   TLS/HTTPS 传输加密                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway / 负载均衡                      │
│              (速率限制、IP 过滤、DDoS 防护)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    认证中间件                                │
│              (API Key 验证、JWT 解析)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    授权中间件                                │
│             (资源所有权、权限范围检查)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    业务逻辑层                                │
│               (数据验证、业务规则)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据访问层                                │
│            (加密存储、审计日志、数据隔离)                     │
└─────────────────────────────────────────────────────────────┘
```

## 认证机制

### API Key 认证

#### 密钥格式

```
<issued-key>xxxxxxxx
│  │    │
│  │    └── 随机字符串 (32 字符)
│  └────── 环境标识 (live/test)
└───────── 前缀标识
```

#### 密钥生成

```python
import secrets
import hashlib
import bcrypt

def generate_api_key(prefix: str = "sk_live") -> tuple[str, str]:
    """
    生成 API 密钥
    
    Returns:
        tuple: (完整密钥, 前缀用于显示)
    """
    # 生成随机字符串
    random_part = secrets.token_urlsafe(24)  # 32 字符
    
    # 组合完整密钥
    api_key = f"{prefix}_{random_part}"
    
    # 生成前缀用于显示 (如 sk_live_abc...)
    key_prefix = f"{prefix}_{random_part[:8]}..."
    
    return api_key, key_prefix

def hash_api_key(api_key: str) -> str:
    """
    哈希 API 密钥 (存储用)
    
    注意: bcrypt 有 72 字节限制，超长密钥会被截断
    """
    # 使用 SHA-256 预处理，确保长度一致
    key_bytes = hashlib.sha256(api_key.encode()).digest()
    
    # 使用 bcrypt 哈希
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(key_bytes, salt)
    
    return hashed.decode()

def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """验证 API 密钥"""
    key_bytes = hashlib.sha256(plain_key.encode()).digest()
    return bcrypt.checkpw(key_bytes, hashed_key.encode())
```

#### 密钥存储

```sql
-- API 密钥表设计
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- 只存储前缀和哈希，不存储明文
    key_prefix VARCHAR(20) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    
    -- 权限范围
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    
    -- 状态与过期
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 重要：永远不要存储明文密钥！
```

### JWT Token 认证

#### Token 结构

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user_id",
    "iat": 1234567890,
    "exp": 1234654290,
    "scopes": ["read", "write"],
    "jti": "unique_token_id"
  },
  "signature": "..."
}
```

#### Token 生成与验证

```python
import jwt
from datetime import datetime, timedelta
from typing import Optional

SECRET_KEY = "your-secret-key-at-least-32-characters"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())
    })
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    """解码并验证 JWT"""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
```

## 授权模型

### 资源所有权

```python
class ResourceOwnership:
    """资源所有权验证"""
    
    @staticmethod
    async def verify_file_access(
        user_id: str,
        file_id: str,
        required_permission: str = "read"
    ) -> bool:
        """验证用户对文件的访问权限"""
        
        file = await get_file_by_id(file_id)
        if not file:
            raise ResourceNotFoundError(f"File {file_id} not found")
        
        # 检查所有权
        if file.user_id != user_id:
            raise ForbiddenError("Access denied to this resource")
        
        return True
    
    @staticmethod
    async def verify_kb_access(
        user_id: str,
        kb_id: str,
        required_permission: str = "read"
    ) -> bool:
        """验证用户对知识库的访问权限"""
        
        kb = await get_knowledge_base_by_id(kb_id)
        if not kb:
            raise ResourceNotFoundError(f"Knowledge base {kb_id} not found")
        
        if kb.user_id != user_id:
            raise ForbiddenError("Access denied to this resource")
        
        return True
```

### 权限范围 (Scopes)

```python
from enum import Enum

class Scope(str, Enum):
    # 读取权限
    READ = "read"
    READ_FILES = "files:read"
    READ_KB = "knowledge_bases:read"
    
    # 写入权限
    WRITE = "write"
    WRITE_FILES = "files:write"
    WRITE_KB = "knowledge_bases:write"
    
    # 删除权限
    DELETE = "delete"
    DELETE_FILES = "files:delete"
    DELETE_KB = "knowledge_bases:delete"
    
    # 管理权限
    ADMIN = "admin"
    MANAGE_API_KEYS = "api_keys:manage"
    MANAGE_WEBHOOKS = "webhooks:manage"

def check_scope(required: Scope, granted: list[str]) -> bool:
    """检查是否有所需权限"""
    
    # 超级权限检查
    if "admin" in granted:
        return True
    
    if required.value in granted:
        return True
    
    # 检查通配符权限
    # 例如 "write" 授予所有写入权限
    if required.value.endswith(":read") and "read" in granted:
        return True
    if required.value.endswith(":write") and "write" in granted:
        return True
    if required.value.endswith(":delete") and "delete" in granted:
        return True
    
    return False
```

### 中间件实现

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""
    
    # 无需认证的路径
    PUBLIC_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/api/v1/auth/login"
    ]
    
    async def dispatch(self, request: Request, call_next):
        # 跳过公开路径
        if any(request.url.path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # 提取认证信息
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(
                status_code=401,
                detail="Missing authorization header"
            )
        
        try:
            scheme, token = auth_header.split(" ", 1)
        except ValueError:
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        # API Key 认证
        if scheme.lower() == "bearer" and token.startswith("sk_"):
            user = await self._authenticate_api_key(token)
        # JWT 认证
        elif scheme.lower() == "bearer":
            user = await self._authenticate_jwt(token)
        else:
            raise HTTPException(
                status_code=401,
                detail="Unsupported authentication scheme"
            )
        
        # 将用户信息附加到请求
        request.state.user = user
        
        return await call_next(request)
    
    async def _authenticate_api_key(self, api_key: str) -> User:
        """验证 API Key"""
        # 提取前缀
        prefix = api_key[:12]  # [REDACTED]
        
        # 查找匹配的密钥
        key_record = await find_api_key_by_prefix(prefix)
        
        if not key_record:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if not key_record.is_active:
            raise HTTPException(status_code=401, detail="API key is inactive")
        
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key has expired")
        
        # 验证哈希
        if not verify_api_key(api_key, key_record.key_hash):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # 更新最后使用时间
        await update_api_key_last_used(key_record.id)
        
        # 获取用户信息
        user = await get_user_by_id(key_record.user_id)
        user.scopes = key_record.scopes
        
        return user
    
    async def _authenticate_jwt(self, token: str) -> User:
        """验证 JWT"""
        payload = decode_access_token(token)
        
        user = await get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user.scopes = payload.get("scopes", [])
        
        return user
```

## 数据加密

### 传输加密

```nginx
# nginx TLS 配置
server {
    listen 443 ssl http2;
    server_name api.unifiles.com;
    
    # TLS 证书
    ssl_certificate /etc/ssl/certs/unifiles.crt;
    ssl_certificate_key /etc/ssl/private/unifiles.key;
    
    # TLS 协议版本
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # 加密套件
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000" always;
    
    # 其他安全头
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
```

### 静态加密

```python
from cryptography.fernet import Fernet
import base64
import os

class EncryptionService:
    """对称加密服务 (Fernet)"""
    
    def __init__(self, key: str = None):
        if key:
            # 确保密钥是有效的 Fernet 密钥
            self.key = key.encode() if isinstance(key, str) else key
        else:
            # 从环境变量获取或生成
            env_key = os.environ.get("ENCRYPTION_KEY")
            if env_key:
                self.key = base64.urlsafe_b64decode(env_key)
            else:
                self.key = Fernet.generate_key()
        
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data: str) -> str:
        """加密字符串数据"""
        encrypted = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(decoded)
        return decrypted.decode()
    
    def encrypt_file(self, file_path: str, output_path: str):
        """加密文件"""
        with open(file_path, "rb") as f:
            data = f.read()
        
        encrypted = self.cipher.encrypt(data)
        
        with open(output_path, "wb") as f:
            f.write(encrypted)
    
    def decrypt_file(self, encrypted_path: str, output_path: str):
        """解密文件"""
        with open(encrypted_path, "rb") as f:
            encrypted = f.read()
        
        decrypted = self.cipher.decrypt(encrypted)
        
        with open(output_path, "wb") as f:
            f.write(decrypted)
```

### 敏感数据处理

```python
# 敏感字段加密存储
class User(BaseModel):
    id: UUID
    email: str  # 需要查询，不加密
    email_hash: str  # SHA-256 哈希用于唯一性检查
    
    # 加密存储的字段
    encrypted_name: str  # Fernet 加密
    encrypted_phone: str  # Fernet 加密

# 使用示例
encryption = EncryptionService()

async def create_user(email: str, name: str, phone: str):
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        encrypted_name=encryption.encrypt(name),
        encrypted_phone=encryption.encrypt(phone)
    )
    await save_user(user)

async def get_user_decrypted(user_id: str) -> dict:
    user = await get_user_by_id(user_id)
    return {
        "id": user.id,
        "email": user.email,
        "name": encryption.decrypt(user.encrypted_name),
        "phone": encryption.decrypt(user.encrypted_phone)
    }
```

## 安全防护

### 输入验证

```python
from pydantic import BaseModel, validator, constr
import re

class FileUploadRequest(BaseModel):
    filename: constr(max_length=255)
    
    @validator("filename")
    def validate_filename(cls, v):
        # 防止路径遍历
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Invalid filename")
        
        # 只允许安全字符
        if not re.match(r"^[\w\-. ]+$", v):
            raise ValueError("Filename contains invalid characters")
        
        return v

class SearchRequest(BaseModel):
    query: constr(min_length=1, max_length=1000)
    
    @validator("query")
    def sanitize_query(cls, v):
        # 移除潜在的注入字符
        # 注意: 这不是 SQL 注入防护，只是基本清理
        dangerous_chars = ["<", ">", "&", '"', "'"]
        for char in dangerous_chars:
            v = v.replace(char, "")
        return v.strip()
```

### SQL 注入防护

```python
# 正确: 使用参数化查询
async def get_file_by_id(file_id: str) -> Optional[File]:
    query = "SELECT * FROM files WHERE id = $1"
    row = await conn.fetchrow(query, file_id)
    return File(**row) if row else None

# 错误: 永远不要这样做！
async def get_file_unsafe(file_id: str):
    query = f"SELECT * FROM files WHERE id = '{file_id}'"  # SQL 注入风险！
    return await conn.fetch(query)

# 正确: 动态查询构建
async def search_files(
    user_id: str,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None
):
    query = "SELECT * FROM files WHERE user_id = $1"
    params = [user_id]
    param_idx = 2
    
    if status:
        query += f" AND status = ${param_idx}"
        params.append(status)
        param_idx += 1
    
    if tags:
        query += f" AND tags && ${param_idx}"
        params.append(tags)
        param_idx += 1
    
    return await conn.fetch(query, *params)
```

### 速率限制

```python
from datetime import datetime
from typing import Optional
import asyncio

class RateLimiter:
    """基于 Redis 的速率限制器"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, dict]:
        """
        检查是否允许请求
        
        Returns:
            tuple: (是否允许, 速率限制信息)
        """
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        # Redis 管道操作
        pipe = self.redis.pipeline()
        
        # 移除过期记录
        pipe.zremrangebyscore(key, 0, window_start)
        
        # 获取当前请求数
        pipe.zcard(key)
        
        # 添加当前请求
        pipe.zadd(key, {str(now): now})
        
        # 设置过期时间
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_count = results[1]
        
        allowed = current_count < limit
        
        return allowed, {
            "limit": limit,
            "remaining": max(0, limit - current_count - 1),
            "reset": int(now + window_seconds)
        }

# 中间件使用
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 获取限制键 (用户 ID 或 IP)
        user = getattr(request.state, "user", None)
        if user:
            key = f"rate_limit:user:{user.id}"
            limit = user.rate_limit or 1000
        else:
            key = f"rate_limit:ip:{request.client.host}"
            limit = 100  # 匿名用户限制
        
        limiter = RateLimiter(redis_client)
        allowed, info = await limiter.is_allowed(key, limit)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"])
                }
            )
        
        response = await call_next(request)
        
        # 添加速率限制头
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response
```

## 审计日志

### 日志结构

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

@dataclass
class AuditLog:
    id: str
    timestamp: datetime
    
    # 操作信息
    action: str  # CREATE, READ, UPDATE, DELETE
    resource_type: str  # file, knowledge_base, api_key
    resource_id: str
    
    # 用户信息
    user_id: str
    ip_address: str
    user_agent: str
    
    # 请求信息
    method: str
    path: str
    query_params: dict
    
    # 结果
    status_code: int
    success: bool
    error_message: Optional[str]
    
    # 变更详情
    changes: Optional[dict]  # {field: {old: x, new: y}}
    
    # 元数据
    metadata: dict

# 审计日志记录
async def log_audit(
    action: str,
    resource_type: str,
    resource_id: str,
    request: Request,
    success: bool = True,
    error_message: str = None,
    changes: dict = None
):
    log = AuditLog(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=request.state.user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        method=request.method,
        path=request.url.path,
        query_params=dict(request.query_params),
        status_code=200 if success else 400,
        success=success,
        error_message=error_message,
        changes=changes,
        metadata={}
    )
    
    await save_audit_log(log)
```

### 使用示例

```python
@router.delete("/files/{file_id}")
async def delete_file(file_id: str, request: Request):
    user = request.state.user
    
    # 执行删除
    try:
        file = await get_file(file_id)
        await soft_delete_file(file_id, user.id)
        
        # 记录审计日志
        await log_audit(
            action="DELETE",
            resource_type="file",
            resource_id=file_id,
            request=request,
            success=True,
            changes={
                "status": {"old": file.status, "new": "deleted"}
            }
        )
        
        return {"success": True}
        
    except Exception as e:
        # 记录失败日志
        await log_audit(
            action="DELETE",
            resource_type="file",
            resource_id=file_id,
            request=request,
            success=False,
            error_message=str(e)
        )
        raise
```

## 安全检查清单

### 部署前检查

- [ ] 所有密钥已更换为生产值
- [ ] 数据库密码强度足够
- [ ] TLS 证书已配置
- [ ] 敏感环境变量未提交到代码库
- [ ] 默认账户已禁用或更改密码
- [ ] 调试模式已关闭
- [ ] 错误消息不泄露敏感信息
- [ ] 日志不包含敏感数据

### 定期审查

- [ ] API 密钥轮换
- [ ] 依赖漏洞扫描
- [ ] 访问日志审查
- [ ] 权限配置审计
- [ ] 备份恢复测试

## 下一步

- [开发技巧](./development-tips.md) - 本地开发安全实践
- [自部署指南](../self-hosting/index.md) - 生产环境安全配置
