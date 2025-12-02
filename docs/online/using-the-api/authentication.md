# 认证方式

Unifiles 使用 API Key 进行身份认证。本文介绍如何获取和使用 API Key。

## API Key 概述

API Key 是访问 Unifiles API 的凭证，格式为：

```
[REDACTED]xxxxxxxxxxxxxxxxxxxxxxxxx
```

- 前缀 `sk_` 表示 Secret Key
- `live` 表示生产环境（`test` 表示测试环境）
- 后续为随机字符串

!!! warning "安全提示"
    API Key 应当妥善保管，不要在客户端代码或版本控制中暴露。

---

## 获取 API Key

### SaaS 用户

1. 登录 [Unifiles 控制台](https://console.unifiles.dev)
2. 进入「设置」→「API 密钥」
3. 点击「创建新密钥」
4. 复制并安全保存密钥（只会显示一次）

### 自部署用户

使用 CLI 创建 API Key：

```bash
# 创建用户
python -m unifiles.cli create-user --username admin --email admin@example.com

# 创建 API Key
python -m unifiles.cli create-api-key --user admin --name "production"
```

或通过 API 创建（需要管理员权限）：

```bash
curl -X POST "http://localhost:8088/v1/api-keys" \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-key",
    "scopes": ["files:*", "kb:*"],
    "expires_in_days": 365
  }'
```

---

## 使用 API Key

### Python SDK

```python
from unifiles import UnifilesClient

# 方式 1: 直接传入
client = UnifilesClient(api_key="[REDACTED]")

# 方式 2: 从环境变量读取（推荐）
import os
client = UnifilesClient(api_key=os.environ["UNIFILES_API_KEY"])

# 方式 3: 自动读取环境变量
# 设置环境变量 UNIFILES_API_KEY 后，可以省略参数
client = UnifilesClient()
```

### REST API

在请求头中添加 `Authorization` 字段：

```bash
curl -X GET "https://api.unifiles.dev/v1/files" \
  -H "Authorization: Bearer [REDACTED]"
```

### 环境变量配置

推荐使用环境变量管理 API Key：

=== "Linux/macOS"

    ```bash
    export UNIFILES_API_KEY="[REDACTED]"
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:UNIFILES_API_KEY = "[REDACTED]"
    ```

=== ".env 文件"

    ```env
    UNIFILES_API_KEY=[REDACTED]
    ```

    使用 python-dotenv 加载：
    
    ```python
    from dotenv import load_dotenv
    load_dotenv()
    
    from unifiles import UnifilesClient
    client = UnifilesClient()  # 自动读取环境变量
    ```

---

## 权限范围（Scopes）

API Key 可以配置不同的权限范围，限制其访问能力：

| Scope | 说明 |
|-------|------|
| `files:read` | 读取文件信息和下载 |
| `files:write` | 上传和删除文件 |
| `files:*` | 文件的所有权限 |
| `extractions:read` | 读取提取结果 |
| `extractions:write` | 创建提取任务 |
| `extractions:*` | 提取的所有权限 |
| `kb:read` | 读取知识库和搜索 |
| `kb:write` | 创建和修改知识库 |
| `kb:*` | 知识库的所有权限 |
| `api-keys:*` | 管理 API 密钥 |
| `webhooks:*` | 管理 Webhooks |
| `*` | 所有权限 |

### 创建限制权限的 Key

```python
# 使用管理员 Key
admin_client = UnifilesClient(api_key="[REDACTED]")

# 创建只读 Key
readonly_key = admin_client.api_keys.create(
    name="readonly-key",
    scopes=["files:read", "kb:read"]
)

# 创建只能搜索的 Key
search_key = admin_client.api_keys.create(
    name="search-only",
    scopes=["kb:read"]
)
```

---

## API Key 管理

### 列出所有 Key

```python
keys = client.api_keys.list()
for key in keys.items:
    print(f"{key.id}: {key.name} - {key.scopes}")
```

### 撤销 Key

```python
client.api_keys.delete(key_id="key_xxx")
```

### 设置过期时间

```python
key = client.api_keys.create(
    name="temp-key",
    scopes=["files:*"],
    expires_in_days=7  # 7 天后过期
)

print(f"过期时间: {key.expires_at}")
```

---

## 安全最佳实践

### 1. 使用环境变量

不要在代码中硬编码 API Key：

```python
# ❌ 不要这样做
client = UnifilesClient(api_key="[REDACTED]...")

# ✅ 推荐做法
import os
client = UnifilesClient(api_key=os.environ["UNIFILES_API_KEY"])
```

### 2. 限制权限范围

为每个应用创建专用 Key，只授予必要的权限：

```python
# 为搜索服务创建只读 Key
search_key = admin_client.api_keys.create(
    name="search-service",
    scopes=["kb:read"]  # 只能搜索，不能修改
)

# 为上传服务创建写入 Key
upload_key = admin_client.api_keys.create(
    name="upload-service",
    scopes=["files:write", "extractions:write"]
)
```

### 3. 定期轮换

定期更换 API Key，降低泄露风险：

```python
# 创建新 Key
new_key = admin_client.api_keys.create(
    name="production-v2",
    scopes=["*"]
)

# 更新应用配置使用新 Key
# ...

# 撤销旧 Key
admin_client.api_keys.delete(old_key_id)
```

### 4. 使用 IP 白名单

限制 API Key 只能从特定 IP 访问：

```python
key = admin_client.api_keys.create(
    name="production",
    scopes=["*"],
    allowed_ips=["203.0.113.0/24", "198.51.100.1"]
)
```

### 5. 监控使用情况

定期检查 API Key 的使用情况：

```python
usage = client.usage.stats(
    start_date="2024-01-01",
    end_date="2024-01-31"
)

print(f"API 调用次数: {usage.total_requests}")
print(f"文件上传量: {usage.files_uploaded}")
```

---

## 常见问题

??? question "API Key 泄露了怎么办？"

    1. 立即撤销泄露的 Key：
       ```python
       admin_client.api_keys.delete(compromised_key_id)
       ```
    2. 创建新的 API Key
    3. 更新所有使用该 Key 的应用
    4. 检查是否有异常活动

??? question "如何在多环境中管理 Key？"

    为每个环境创建独立的 Key：
    
    - 开发环境：`sk_test_dev_...`
    - 测试环境：`sk_test_staging_...`
    - 生产环境：`sk_live_prod_...`
    
    使用环境变量区分：
    
    ```python
    import os
    
    env = os.environ.get("ENV", "development")
    api_key = os.environ.get(f"UNIFILES_API_KEY_{env.upper()}")
    
    client = UnifilesClient(api_key=api_key)
    ```

??? question "API Key 过期了会怎样？"

    过期的 Key 会返回 401 错误：
    
    ```json
    {
      "success": false,
      "error": {
        "code": "AUTH_KEY_EXPIRED",
        "message": "API key has expired"
      }
    }
    ```
    
    需要创建新的 Key 并更新应用配置。

---

## 下一步

<div class="grid cards" markdown>

-   :material-file-upload: **文件和上传**
    
    开始上传和管理文件
    
    [:octicons-arrow-right-24: files-and-uploads.md](./files-and-uploads.md)

-   :material-alert-circle: **错误处理**
    
    了解如何处理 API 错误
    
    [:octicons-arrow-right-24: error-handling.md](./error-handling.md)

</div>
