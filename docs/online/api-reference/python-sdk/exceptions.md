# 异常类型

SDK 异常类层次结构和使用方法。

## 异常层次

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

## 基类

### UnifilesError

```python
class UnifilesError(Exception):
    code: str              # 错误码
    message: str           # 错误信息
    status_code: int       # HTTP 状态码
    request_id: str        # 请求 ID
    details: Optional[Dict] # 详细信息
```

## 具体异常

### AuthenticationError

认证失败。

```python
from unifiles.exceptions import AuthenticationError

try:
    client.files.list()
except AuthenticationError as e:
    print(f"认证失败: {e.message}")
    # e.code: INVALID_API_KEY, EXPIRED_API_KEY, etc.
```

### PermissionError

权限不足。

```python
from unifiles.exceptions import PermissionError

try:
    client.files.delete(file_id)
except PermissionError as e:
    if e.code == "INSUFFICIENT_SCOPE":
        print("API Key 权限不足")
    elif e.code == "QUOTA_EXCEEDED":
        print("配额已用完")
```

### NotFoundError

资源不存在。

```python
from unifiles.exceptions import NotFoundError

try:
    file = client.files.get("invalid_id")
except NotFoundError as e:
    print(f"资源不存在: {e.message}")
    # e.code: FILE_NOT_FOUND, KB_NOT_FOUND, etc.
```

### ValidationError

请求参数验证失败。

```python
from unifiles.exceptions import ValidationError

try:
    kb = client.knowledge_bases.create(name="")
except ValidationError as e:
    print(f"参数错误: {e.message}")
    if e.details:
        print(f"字段: {e.details.get('field')}")
```

### ProcessingError

文件处理失败。

```python
from unifiles.exceptions import ProcessingError

try:
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
except ProcessingError as e:
    if e.code == "OCR_FAILED":
        print("OCR 识别失败")
    elif e.code == "ENCRYPTED_FILE":
        print("文件有密码保护")
```

### RateLimitError

超出速率限制。

```python
from unifiles.exceptions import RateLimitError
import time

try:
    result = client.files.upload("doc.pdf")
except RateLimitError as e:
    print(f"请求过于频繁")
    print(f"请在 {e.retry_after} 秒后重试")
    time.sleep(e.retry_after)
```

**属性：**
- `retry_after: int` - 建议等待秒数

### ServerError

服务器内部错误。

```python
from unifiles.exceptions import ServerError

try:
    result = client.files.list()
except ServerError as e:
    print(f"服务器错误: {e.message}")
    print(f"请求 ID: {e.request_id}")  # 用于排查
```

### TimeoutError

请求超时。

```python
from unifiles.exceptions import TimeoutError

try:
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait(timeout=60)
except TimeoutError as e:
    print("请求超时")
```

## 完整错误处理示例

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
import time

client = UnifilesClient(api_key="<api-key>")

def safe_upload(file_path: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return client.files.upload(file_path)
            
        except AuthenticationError:
            raise  # 不重试认证错误
            
        except ValidationError as e:
            raise  # 不重试参数错误
            
        except RateLimitError as e:
            if attempt < max_retries - 1:
                time.sleep(e.retry_after or 60)
            else:
                raise
                
        except (ServerError, TimeoutError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                raise
                
        except UnifilesError as e:
            print(f"未知错误: {e.code} - {e.message}")
            raise
```

## 导入

```python
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
```
