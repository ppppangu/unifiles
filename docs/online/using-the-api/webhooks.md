# Webhooks

Webhooks 允许你在 Unifiles 中的异步操作完成时接收实时通知，无需轮询 API 查询状态。

## 工作原理

```
1. 你配置 Webhook URL 和订阅的事件
2. 当事件发生时，Unifiles 向你的 URL 发送 HTTP POST 请求
3. 你的服务器处理通知并返回 200 状态码
4. 如果失败，Unifiles 会自动重试
```

## SDK 使用

### 创建 Webhook

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 创建 Webhook
webhook = client.webhooks.create(
    url="https://your-app.com/webhook/unifiles",
    events=[
        "extraction.completed",
        "extraction.failed",
        "document.indexed",
        "document.index_failed"
    ],
    secret="your_webhook_secret"  # 用于验证签名
)

print(f"Webhook ID: {webhook.id}")
print(f"URL: {webhook.url}")
print(f"Events: {webhook.events}")
```

### 列出 Webhooks

```python
webhooks = client.webhooks.list()

for wh in webhooks.items:
    print(f"{wh.id}: {wh.url}")
    print(f"  事件: {wh.events}")
    print(f"  状态: {'启用' if wh.enabled else '禁用'}")
```

### 获取 Webhook 详情

```python
webhook = client.webhooks.get(webhook_id)

print(f"URL: {webhook.url}")
print(f"事件: {webhook.events}")
print(f"创建时间: {webhook.created_at}")
print(f"最近投递: {webhook.last_delivery_at}")
```

### 更新 Webhook

```python
webhook = client.webhooks.update(
    webhook_id=webhook.id,
    events=["extraction.completed"],  # 只订阅提取完成
    enabled=True
)
```

### 删除 Webhook

```python
client.webhooks.delete(webhook_id)
```

## REST API

### 创建 Webhook

```http
POST /v1/webhooks
Authorization: Bearer sk_...
Content-Type: application/json

{
    "url": "https://your-app.com/webhook/unifiles",
    "events": ["extraction.completed", "document.indexed"],
    "secret": "your_webhook_secret"
}
```

**响应：**

```json
{
    "id": "wh_abc123",
    "url": "https://your-app.com/webhook/unifiles",
    "events": ["extraction.completed", "document.indexed"],
    "enabled": true,
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 列出 Webhooks

```http
GET /v1/webhooks
Authorization: Bearer sk_...
```

### 获取 Webhook

```http
GET /v1/webhooks/{webhook_id}
Authorization: Bearer sk_...
```

### 更新 Webhook

```http
PATCH /v1/webhooks/{webhook_id}
Authorization: Bearer sk_...
Content-Type: application/json

{
    "events": ["extraction.completed"],
    "enabled": true
}
```

### 删除 Webhook

```http
DELETE /v1/webhooks/{webhook_id}
Authorization: Bearer sk_...
```

## 支持的事件

### 文件事件

| 事件 | 说明 |
|-----|------|
| `file.uploaded` | 文件上传成功 |
| `file.deleted` | 文件被删除 |

### 提取事件

| 事件 | 说明 |
|-----|------|
| `extraction.started` | 提取任务开始处理 |
| `extraction.completed` | 提取成功完成 |
| `extraction.failed` | 提取失败 |

### 文档事件

| 事件 | 说明 |
|-----|------|
| `document.indexing` | 文档开始索引 |
| `document.indexed` | 文档索引完成 |
| `document.index_failed` | 文档索引失败 |
| `document.deleted` | 文档从知识库删除 |

### 知识库事件

| 事件 | 说明 |
|-----|------|
| `knowledge_base.created` | 知识库创建 |
| `knowledge_base.deleted` | 知识库删除 |

## Webhook 请求格式

当事件触发时，Unifiles 会向你的 URL 发送如下请求：

```http
POST /webhook/unifiles HTTP/1.1
Host: your-app.com
Content-Type: application/json
X-Unifiles-Signature: sha256=abc123...
X-Unifiles-Event: extraction.completed
X-Unifiles-Delivery: del_xyz789

{
    "id": "evt_abc123",
    "type": "extraction.completed",
    "created_at": "2024-01-15T10:35:00Z",
    "data": {
        "extraction_id": "ext_xyz789",
        "file_id": "file_abc123",
        "status": "completed",
        "total_pages": 15
    }
}
```

### 请求头

| Header | 说明 |
|--------|------|
| `X-Unifiles-Signature` | 请求签名，用于验证真实性 |
| `X-Unifiles-Event` | 事件类型 |
| `X-Unifiles-Delivery` | 投递ID，用于排查问题 |

### 事件数据结构

**extraction.completed：**

```json
{
    "id": "evt_abc123",
    "type": "extraction.completed",
    "created_at": "2024-01-15T10:35:00Z",
    "data": {
        "extraction_id": "ext_xyz789",
        "file_id": "file_abc123",
        "status": "completed",
        "total_pages": 15,
        "markdown_length": 25600
    }
}
```

**extraction.failed：**

```json
{
    "id": "evt_def456",
    "type": "extraction.failed",
    "created_at": "2024-01-15T10:36:00Z",
    "data": {
        "extraction_id": "ext_xyz789",
        "file_id": "file_abc123",
        "status": "failed",
        "error": {
            "code": "OCR_FAILED",
            "message": "OCR处理失败"
        }
    }
}
```

**document.indexed：**

```json
{
    "id": "evt_ghi789",
    "type": "document.indexed",
    "created_at": "2024-01-15T10:40:00Z",
    "data": {
        "document_id": "doc_abc123",
        "kb_id": "kb_xyz789",
        "file_id": "file_abc123",
        "chunk_count": 42
    }
}
```

## 签名验证

为确保 Webhook 请求来自 Unifiles，你应该验证请求签名。

### Python 示例

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """验证 Webhook 签名"""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    expected_signature = f"sha256={expected}"
    return hmac.compare_digest(signature, expected_signature)

# Flask 示例
from flask import Flask, request, jsonify

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

@app.route("/webhook/unifiles", methods=["POST"])
def handle_webhook():
    # 获取签名
    signature = request.headers.get("X-Unifiles-Signature")
    if not signature:
        return jsonify({"error": "Missing signature"}), 401
    
    # 验证签名
    if not verify_webhook_signature(request.data, signature, WEBHOOK_SECRET):
        return jsonify({"error": "Invalid signature"}), 401
    
    # 处理事件
    event = request.json
    event_type = event["type"]
    
    if event_type == "extraction.completed":
        handle_extraction_completed(event["data"])
    elif event_type == "document.indexed":
        handle_document_indexed(event["data"])
    
    return jsonify({"received": True}), 200

def handle_extraction_completed(data):
    print(f"提取完成: {data['extraction_id']}")
    # 你的业务逻辑

def handle_document_indexed(data):
    print(f"索引完成: {data['document_id']}")
    # 你的业务逻辑
```

### FastAPI 示例

```python
from fastapi import FastAPI, Request, HTTPException, Header
import hmac
import hashlib

app = FastAPI()
WEBHOOK_SECRET = "your_webhook_secret"

def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected}")

@app.post("/webhook/unifiles")
async def handle_webhook(
    request: Request,
    x_unifiles_signature: str = Header(...)
):
    payload = await request.body()
    
    if not verify_signature(payload, x_unifiles_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    event = await request.json()
    
    # 处理事件
    match event["type"]:
        case "extraction.completed":
            await process_extraction(event["data"])
        case "document.indexed":
            await process_indexed(event["data"])
    
    return {"received": True}
```

## 重试机制

如果你的服务器返回非 2xx 状态码或无响应，Unifiles 会自动重试：

| 重试次数 | 延迟 |
|---------|------|
| 第1次 | 立即 |
| 第2次 | 1分钟后 |
| 第3次 | 5分钟后 |
| 第4次 | 30分钟后 |
| 第5次 | 2小时后 |

超过5次重试后，该投递将被标记为失败。

### 响应要求

- 在 **30秒内** 返回响应
- 返回 **2xx 状态码** 表示成功
- 响应体可以为空或返回任意内容

### 最佳实践

```python
@app.post("/webhook/unifiles")
async def handle_webhook(request: Request):
    event = await request.json()
    
    # 立即返回200，然后异步处理
    # 避免超时
    background_tasks.add_task(process_event, event)
    
    return {"received": True}

async def process_event(event):
    """异步处理事件，不阻塞响应"""
    # 耗时的业务逻辑
    pass
```

## 常见使用场景

### 1. 批量处理完成通知

```python
# 批量上传文件，通过 Webhook 获取完成通知
for path in file_paths:
    file = client.files.upload(path)
    extraction = client.extractions.create(file_id=file.id)
    # 不等待，继续上传下一个

# Webhook 处理器
@app.post("/webhook/unifiles")
async def webhook(request: Request):
    event = await request.json()
    
    if event["type"] == "extraction.completed":
        data = event["data"]
        # 更新你的数据库
        await db.update_file_status(
            file_id=data["file_id"],
            status="extracted"
        )
        # 通知用户
        await notify_user(data["file_id"])
    
    return {"ok": True}
```

### 2. 自动索引到知识库

```python
@app.post("/webhook/unifiles")
async def webhook(request: Request):
    event = await request.json()
    
    if event["type"] == "extraction.completed":
        data = event["data"]
        
        # 提取完成后自动添加到知识库
        client.knowledge_bases.documents.create(
            kb_id="kb_default",
            file_id=data["file_id"]
        )
    
    return {"ok": True}
```

### 3. 错误告警

```python
import requests

SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

@app.post("/webhook/unifiles")
async def webhook(request: Request):
    event = await request.json()
    
    if event["type"] in ["extraction.failed", "document.index_failed"]:
        # 发送 Slack 告警
        requests.post(SLACK_WEBHOOK, json={
            "text": f"⚠️ Unifiles 处理失败\n"
                   f"类型: {event['type']}\n"
                   f"错误: {event['data'].get('error', {}).get('message')}"
        })
    
    return {"ok": True}
```

## 调试 Webhooks

### 查看投递历史

```python
# 获取 Webhook 的投递历史
deliveries = client.webhooks.deliveries(webhook_id, limit=20)

for d in deliveries.items:
    print(f"投递ID: {d.id}")
    print(f"事件: {d.event_type}")
    print(f"状态: {d.status}")
    print(f"响应码: {d.response_status}")
    print(f"时间: {d.created_at}")
```

### 重新发送投递

```python
# 重新发送某次投递
client.webhooks.redeliver(webhook_id, delivery_id)
```

### 本地开发测试

使用 ngrok 等工具将本地服务暴露到公网：

```bash
# 启动 ngrok
ngrok http 8000

# 获取公网URL，例如：https://abc123.ngrok.io
# 将此URL配置为 Webhook URL
```

## 下一步

- [速率限制](rate-limits.md) - 了解 API 调用限制
- [错误处理](error-handling.md) - 处理 Webhook 中的错误
- [批量处理](../cookbook/intermediate/batch-processing.md) - 结合 Webhook 的批处理最佳实践
