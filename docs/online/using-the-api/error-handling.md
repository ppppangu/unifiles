# 错误处理

本文档介绍 Unifiles API 的错误响应格式、常见错误码以及最佳处理实践。

## 错误响应格式

所有 API 错误都遵循统一的响应格式：

```json
{
    "success": false,
    "error": {
        "code": "INVALID_REQUEST",
        "message": "请求参数无效",
        "details": {
            "field": "file_id",
            "reason": "文件ID格式不正确"
        },
        "request_id": "req_abc123xyz"
    }
}
```

| 字段 | 类型 | 说明 |
|-----|------|------|
| `code` | string | 错误码，用于程序处理 |
| `message` | string | 人类可读的错误描述 |
| `details` | object | 可选，错误的详细信息 |
| `request_id` | string | 请求ID，用于排查问题 |

## HTTP 状态码

| 状态码 | 说明 | 常见场景 |
|-------|------|---------|
| `400` | Bad Request | 请求参数错误 |
| `401` | Unauthorized | 未提供或无效的 API Key |
| `403` | Forbidden | 权限不足 |
| `404` | Not Found | 资源不存在 |
| `409` | Conflict | 资源冲突 |
| `413` | Payload Too Large | 请求体过大 |
| `415` | Unsupported Media Type | 不支持的文件格式 |
| `422` | Unprocessable Entity | 业务逻辑错误 |
| `429` | Too Many Requests | 超出速率限制 |
| `500` | Internal Server Error | 服务器内部错误 |

## 错误码参考

### 认证错误 (401)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `INVALID_API_KEY` | API Key 无效 | 检查 API Key 是否正确 |
| `EXPIRED_API_KEY` | API Key 已过期 | 重新生成 API Key |
| `REVOKED_API_KEY` | API Key 已被撤销 | 联系管理员或创建新 Key |
| `MISSING_API_KEY` | 未提供认证信息 | 添加 Authorization 头 |

```python
from unifiles.exceptions import AuthenticationError

try:
    client.files.list()
except AuthenticationError as e:
    if e.code == "INVALID_API_KEY":
        print("API Key 无效，请检查配置")
    elif e.code == "EXPIRED_API_KEY":
        print("API Key 已过期，请重新生成")
```

### 权限错误 (403)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `INSUFFICIENT_SCOPE` | API Key 权限不足 | 使用具有相应权限的 Key |
| `RESOURCE_ACCESS_DENIED` | 无权访问该资源 | 检查资源所有权 |
| `QUOTA_EXCEEDED` | 配额已用完 | 升级计划或等待重置 |

```python
from unifiles.exceptions import PermissionError

try:
    client.files.delete(file_id)
except PermissionError as e:
    if e.code == "INSUFFICIENT_SCOPE":
        print("当前 API Key 没有删除权限")
    elif e.code == "QUOTA_EXCEEDED":
        print("存储配额已满，请清理文件或升级计划")
```

### 资源错误 (404)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `FILE_NOT_FOUND` | 文件不存在 | 检查文件ID是否正确 |
| `EXTRACTION_NOT_FOUND` | 提取任务不存在 | 检查提取ID |
| `KNOWLEDGE_BASE_NOT_FOUND` | 知识库不存在 | 检查知识库ID |
| `DOCUMENT_NOT_FOUND` | 文档不存在 | 检查文档ID |
| `WEBHOOK_NOT_FOUND` | Webhook 不存在 | 检查 Webhook ID |

```python
from unifiles.exceptions import NotFoundError

try:
    file = client.files.get(file_id)
except NotFoundError as e:
    if e.code == "FILE_NOT_FOUND":
        print(f"文件 {file_id} 不存在")
```

### 请求错误 (400/422)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `INVALID_REQUEST` | 请求格式错误 | 检查请求参数 |
| `INVALID_FILE_ID` | 文件ID格式无效 | 使用正确的ID格式 |
| `INVALID_PARAMETER` | 参数值无效 | 检查参数范围和类型 |
| `MISSING_PARAMETER` | 缺少必需参数 | 补充必需参数 |
| `INVALID_FILE_TYPE` | 不支持的文件类型 | 使用支持的文件格式 |
| `FILE_TOO_LARGE` | 文件过大 | 压缩文件或分片上传 |
| `EXTRACTION_NOT_COMPLETED` | 提取未完成 | 等待提取完成后操作 |
| `DUPLICATE_DOCUMENT` | 文档已存在于知识库 | 先删除或使用更新操作 |

```python
from unifiles.exceptions import ValidationError

try:
    kb = client.knowledge_bases.create(
        name="",  # 空名称
        chunking_strategy={"type": "invalid"}
    )
except ValidationError as e:
    print(f"参数错误: {e.message}")
    if e.details:
        print(f"问题字段: {e.details.get('field')}")
        print(f"原因: {e.details.get('reason')}")
```

### 文件处理错误 (422)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `UNSUPPORTED_FORMAT` | 不支持的文件格式 | 检查支持的格式列表 |
| `CORRUPTED_FILE` | 文件已损坏 | 重新上传原始文件 |
| `ENCRYPTED_FILE` | 文件有密码保护 | 移除密码后重试 |
| `EMPTY_FILE` | 文件内容为空 | 检查文件内容 |
| `OCR_FAILED` | OCR 识别失败 | 尝试不同的提取模式 |
| `EXTRACTION_TIMEOUT` | 提取超时 | 重试或使用更简单的模式 |

```python
from unifiles.exceptions import ProcessingError

try:
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
except ProcessingError as e:
    if e.code == "OCR_FAILED":
        # 尝试降级到 simple 模式
        extraction = client.extractions.create(
            file_id=file.id,
            mode="simple"
        )
    elif e.code == "ENCRYPTED_FILE":
        print("请移除文件密码后重新上传")
```

### 速率限制错误 (429)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `RATE_LIMIT_EXCEEDED` | 请求频率超限 | 等待后重试 |
| `CONCURRENT_LIMIT_EXCEEDED` | 并发请求超限 | 减少并发数 |

```python
from unifiles.exceptions import RateLimitError
import time

try:
    result = client.files.upload("document.pdf")
except RateLimitError as e:
    wait_time = e.retry_after or 60
    print(f"请求过于频繁，{wait_time}秒后重试")
    time.sleep(wait_time)
    # 重试
    result = client.files.upload("document.pdf")
```

### 服务器错误 (500+)

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| `INTERNAL_ERROR` | 内部服务错误 | 稍后重试 |
| `SERVICE_UNAVAILABLE` | 服务暂时不可用 | 稍后重试 |
| `DATABASE_ERROR` | 数据库错误 | 稍后重试 |
| `STORAGE_ERROR` | 存储服务错误 | 稍后重试 |

```python
from unifiles.exceptions import ServerError

try:
    result = client.files.list()
except ServerError as e:
    if e.code in ["INTERNAL_ERROR", "SERVICE_UNAVAILABLE"]:
        print("服务暂时不可用，请稍后重试")
        # 实现重试逻辑
```

## SDK 异常类层次

```
UnifilesError (基类)
├── AuthenticationError   # 401 认证错误
├── PermissionError       # 403 权限错误  
├── NotFoundError         # 404 资源不存在
├── ValidationError       # 400/422 验证错误
├── ProcessingError       # 422 处理错误
├── RateLimitError        # 429 速率限制
├── ServerError           # 500+ 服务器错误
└── TimeoutError          # 请求超时
```

### 使用示例

```python
from unifiles import UnifilesClient
from unifiles.exceptions import (
    UnifilesError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    ValidationError,
    ProcessingError,
    RateLimitError,
    ServerError,
    TimeoutError
)

client = UnifilesClient(api_key="<api-key>")

try:
    file = client.files.upload("document.pdf")
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
    
except AuthenticationError as e:
    # 认证问题
    print(f"认证失败: {e.message}")
    
except PermissionError as e:
    # 权限问题
    print(f"权限不足: {e.message}")
    
except NotFoundError as e:
    # 资源不存在
    print(f"资源不存在: {e.message}")
    
except ValidationError as e:
    # 参数验证失败
    print(f"参数错误: {e.message}")
    if e.details:
        print(f"详情: {e.details}")
        
except ProcessingError as e:
    # 文件处理失败
    print(f"处理失败: {e.message}")
    print(f"错误码: {e.code}")
    
except RateLimitError as e:
    # 超出速率限制
    print(f"请求过于频繁，请在 {e.retry_after} 秒后重试")
    
except ServerError as e:
    # 服务器错误
    print(f"服务器错误: {e.message}")
    print(f"请求ID: {e.request_id}")
    
except TimeoutError as e:
    # 请求超时
    print("请求超时，请检查网络或稍后重试")
    
except UnifilesError as e:
    # 其他 Unifiles 错误
    print(f"未知错误: {e.message}")
```

## 最佳实践

### 1. 使用结构化错误处理

```python
def handle_file_upload(file_path: str) -> dict:
    """带完整错误处理的文件上传"""
    try:
        file = client.files.upload(file_path)
        return {"success": True, "file_id": file.id}
        
    except ValidationError as e:
        return {
            "success": False,
            "error_type": "validation",
            "message": e.message,
            "details": e.details
        }
        
    except ProcessingError as e:
        return {
            "success": False, 
            "error_type": "processing",
            "code": e.code,
            "message": e.message
        }
        
    except RateLimitError as e:
        return {
            "success": False,
            "error_type": "rate_limit",
            "retry_after": e.retry_after
        }
        
    except UnifilesError as e:
        return {
            "success": False,
            "error_type": "unknown",
            "message": e.message,
            "request_id": e.request_id
        }
```

### 2. 实现带重试的操作

```python
import time
from typing import TypeVar, Callable

T = TypeVar('T')

def with_retry(
    func: Callable[[], T],
    max_attempts: int = 3,
    retry_on: tuple = (ServerError, TimeoutError, RateLimitError)
) -> T:
    """通用重试装饰器"""
    last_error = None
    
    for attempt in range(max_attempts):
        try:
            return func()
        except retry_on as e:
            last_error = e
            
            if isinstance(e, RateLimitError):
                wait_time = e.retry_after or 60
            else:
                wait_time = 2 ** attempt  # 指数退避
            
            if attempt < max_attempts - 1:
                print(f"尝试 {attempt + 1} 失败，{wait_time}秒后重试...")
                time.sleep(wait_time)
    
    raise last_error

# 使用示例
file = with_retry(lambda: client.files.upload("document.pdf"))
```

### 3. 记录错误日志

```python
import logging

logger = logging.getLogger("unifiles")

def upload_file_with_logging(file_path: str):
    """带日志记录的文件上传"""
    try:
        file = client.files.upload(file_path)
        logger.info(f"文件上传成功: {file.id}")
        return file
        
    except UnifilesError as e:
        logger.error(
            f"文件上传失败",
            extra={
                "file_path": file_path,
                "error_code": e.code,
                "error_message": e.message,
                "request_id": e.request_id
            }
        )
        raise
```

### 4. 优雅降级

```python
def extract_with_fallback(file_id: str) -> str:
    """带降级策略的内容提取"""
    modes = ["advanced", "normal", "simple"]
    
    for mode in modes:
        try:
            extraction = client.extractions.create(
                file_id=file_id,
                mode=mode
            )
            extraction.wait()
            
            if extraction.status == "completed":
                return extraction.markdown
                
        except ProcessingError as e:
            if e.code in ["OCR_FAILED", "EXTRACTION_TIMEOUT"]:
                print(f"{mode}模式失败，尝试降级...")
                continue
            raise
    
    raise Exception("所有提取模式均失败")
```

### 5. 用户友好的错误提示

```python
ERROR_MESSAGES = {
    "INVALID_API_KEY": "API密钥无效，请检查您的配置",
    "QUOTA_EXCEEDED": "您的存储配额已满，请升级计划或清理文件",
    "FILE_TOO_LARGE": "文件大小超过限制（最大100MB）",
    "UNSUPPORTED_FORMAT": "不支持的文件格式，请查看支持的格式列表",
    "RATE_LIMIT_EXCEEDED": "请求过于频繁，请稍后再试",
    "SERVICE_UNAVAILABLE": "服务暂时不可用，请稍后再试"
}

def get_user_friendly_message(error: UnifilesError) -> str:
    """获取用户友好的错误提示"""
    return ERROR_MESSAGES.get(
        error.code,
        f"操作失败: {error.message}"
    )
```

## 调试技巧

### 1. 使用 request_id 排查问题

每个错误响应都包含 `request_id`，联系支持时请提供：

```python
try:
    result = client.files.upload("document.pdf")
except UnifilesError as e:
    print(f"错误: {e.message}")
    print(f"请求ID: {e.request_id}")  # 提供给技术支持
```

### 2. 启用调试日志

```python
import logging

# 启用 SDK 调试日志
logging.getLogger("unifiles").setLevel(logging.DEBUG)

# 查看完整的请求/响应
client = UnifilesClient(
    api_key="<api-key>",
    debug=True  # 启用调试模式
)
```

### 3. 检查响应详情

```python
try:
    result = client.files.upload("document.pdf")
except UnifilesError as e:
    print(f"状态码: {e.status_code}")
    print(f"错误码: {e.code}")
    print(f"错误信息: {e.message}")
    print(f"详情: {e.details}")
    print(f"请求ID: {e.request_id}")
```

## 下一步

- [速率限制](rate-limits.md) - 了解 API 调用限制
- [认证](authentication.md) - API Key 管理
- [Webhooks](webhooks.md) - 异步错误通知
