# Webhook 集成

本教程讲解如何使用 Webhook 构建事件驱动的异步处理流程，这是生产环境中处理大量文档的推荐方式。

## 为什么使用 Webhook？

### 轮询 vs Webhook

```
轮询模式（不推荐）：
Client: 状态？ → Server: 处理中
Client: 状态？ → Server: 处理中
Client: 状态？ → Server: 处理中
Client: 状态？ → Server: 完成！

问题：浪费 API 配额，增加延迟

Webhook 模式（推荐）：
Client: 创建任务 → Server: 收到
... 无需轮询 ...
Server: 完成！ → Client (Webhook)

好处：即时通知，节省资源
```

## 快速开始

### 1. 创建 Webhook

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
    secret="your_webhook_secret_key"
)

print(f"Webhook ID: {webhook.id}")
print(f"URL: {webhook.url}")
print(f"Events: {webhook.events}")
```

### 2. 实现 Webhook 处理器

#### Flask 示例

```python
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret_key"

def verify_signature(payload: bytes, signature: str) -> bool:
    """验证 Webhook 签名"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected}")

@app.route("/webhook/unifiles", methods=["POST"])
def handle_webhook():
    # 验证签名
    signature = request.headers.get("X-Unifiles-Signature", "")
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    # 解析事件
    event = request.json
    event_type = event["type"]
    data = event["data"]
    
    # 处理不同事件
    if event_type == "extraction.completed":
        handle_extraction_completed(data)
    elif event_type == "extraction.failed":
        handle_extraction_failed(data)
    elif event_type == "document.indexed":
        handle_document_indexed(data)
    elif event_type == "document.index_failed":
        handle_document_index_failed(data)
    
    return jsonify({"received": True}), 200

def handle_extraction_completed(data):
    file_id = data["file_id"]
    extraction_id = data["extraction_id"]
    print(f"提取完成: {extraction_id}")
    # 你的业务逻辑：例如自动添加到知识库

def handle_extraction_failed(data):
    file_id = data["file_id"]
    error = data.get("error", {})
    print(f"提取失败: {file_id}, 错误: {error.get('message')}")
    # 你的业务逻辑：例如发送告警

def handle_document_indexed(data):
    doc_id = data["document_id"]
    chunk_count = data["chunk_count"]
    print(f"索引完成: {doc_id}, 分块数: {chunk_count}")
    # 你的业务逻辑

def handle_document_index_failed(data):
    doc_id = data["document_id"]
    error = data.get("error", {})
    print(f"索引失败: {doc_id}")
    # 你的业务逻辑

if __name__ == "__main__":
    app.run(port=5000)
```

#### FastAPI 示例

```python
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
import hmac
import hashlib

app = FastAPI()
WEBHOOK_SECRET = "your_webhook_secret_key"

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
    background_tasks: BackgroundTasks,
    x_unifiles_signature: str = Header(...)
):
    payload = await request.body()
    
    # 验证签名
    if not verify_signature(payload, x_unifiles_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    event = await request.json()
    
    # 立即响应，后台处理
    background_tasks.add_task(process_event, event)
    
    return {"received": True}

async def process_event(event: dict):
    """后台处理事件"""
    event_type = event["type"]
    data = event["data"]
    
    match event_type:
        case "extraction.completed":
            await on_extraction_completed(data)
        case "extraction.failed":
            await on_extraction_failed(data)
        case "document.indexed":
            await on_document_indexed(data)

async def on_extraction_completed(data: dict):
    # 异步处理逻辑
    pass
```

### 3. 使用 Webhook 的异步流程

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 批量上传和处理，无需等待
def process_documents_async(file_paths: list):
    tasks = []
    
    for path in file_paths:
        # 上传
        file = client.files.upload(path)
        
        # 创建提取任务（不等待）
        extraction = client.extractions.create(file_id=file.id)
        
        tasks.append({
            "file_id": file.id,
            "extraction_id": extraction.id
        })
        
        print(f"已提交: {path}")
    
    print(f"\n共提交 {len(tasks)} 个任务")
    print("完成后将通过 Webhook 通知")
    
    return tasks

# 提交任务
tasks = process_documents_async([
    "doc1.pdf",
    "doc2.pdf",
    "doc3.pdf"
])

# Webhook 处理器会在任务完成时被调用
```

## 完整工作流示例

### 自动化文档处理管道

```python
# webhook_handler.py
from flask import Flask, request, jsonify
from unifiles import UnifilesClient
import hmac
import hashlib

app = Flask(__name__)
client = UnifilesClient(api_key="sk_...")

WEBHOOK_SECRET = "your_secret"
DEFAULT_KB_ID = "kb_default"

@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    # 验证签名（省略）
    event = request.json
    
    if event["type"] == "extraction.completed":
        # 提取完成后自动添加到知识库
        file_id = event["data"]["file_id"]
        
        try:
            doc = client.knowledge_bases.documents.create(
                kb_id=DEFAULT_KB_ID,
                file_id=file_id
            )
            print(f"文档已添加到知识库: {doc.id}")
        except Exception as e:
            print(f"添加失败: {e}")
    
    elif event["type"] == "document.indexed":
        # 索引完成后通知业务系统
        doc_id = event["data"]["document_id"]
        chunk_count = event["data"]["chunk_count"]
        
        notify_business_system(doc_id, chunk_count)
    
    elif event["type"] in ["extraction.failed", "document.index_failed"]:
        # 失败时发送告警
        send_alert(event)
    
    return jsonify({"ok": True})

def notify_business_system(doc_id: str, chunk_count: int):
    """通知业务系统文档已就绪"""
    # 调用业务系统 API
    pass

def send_alert(event: dict):
    """发送告警"""
    # 发送 Slack/邮件通知
    pass
```

### 带状态追踪的处理器

```python
from flask import Flask, request, jsonify
import redis
import json

app = Flask(__name__)
redis_client = redis.Redis()

@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    event = request.json
    event_type = event["type"]
    data = event["data"]
    
    # 更新任务状态
    if "file_id" in data:
        task_key = f"unifiles:task:{data['file_id']}"
        
        if event_type == "extraction.completed":
            redis_client.hset(task_key, mapping={
                "extraction_status": "completed",
                "extraction_id": data["extraction_id"],
                "pages": data.get("total_pages", 0)
            })
        
        elif event_type == "document.indexed":
            redis_client.hset(task_key, mapping={
                "index_status": "completed",
                "document_id": data["document_id"],
                "chunks": data.get("chunk_count", 0)
            })
            
            # 检查是否全部完成
            task = redis_client.hgetall(task_key)
            if task.get(b"extraction_status") == b"completed" and \
               task.get(b"index_status") == b"completed":
                # 任务全部完成
                on_task_completed(data["file_id"], task)
    
    return jsonify({"ok": True})

def on_task_completed(file_id: str, task: dict):
    """所有步骤完成后的处理"""
    print(f"文件处理完成: {file_id}")
    # 通知用户、更新数据库等
```

## 本地开发调试

### 使用 ngrok

```bash
# 1. 启动本地服务
python webhook_handler.py  # 监听 localhost:5000

# 2. 启动 ngrok
ngrok http 5000

# 3. 获取公网 URL
# https://abc123.ngrok.io

# 4. 配置 Webhook
```

```python
webhook = client.webhooks.create(
    url="https://abc123.ngrok.io/webhook/unifiles",
    events=["extraction.completed"],
    secret="test_secret"
)
```

### 手动测试 Webhook

```python
import requests
import hmac
import hashlib
import json

def test_webhook():
    """本地测试 Webhook 处理器"""
    url = "http://localhost:5000/webhook/unifiles"
    secret = "your_secret"
    
    payload = {
        "id": "evt_test123",
        "type": "extraction.completed",
        "data": {
            "extraction_id": "ext_test",
            "file_id": "file_test",
            "status": "completed"
        }
    }
    
    payload_bytes = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    response = requests.post(
        url,
        json=payload,
        headers={"X-Unifiles-Signature": signature}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

test_webhook()
```

## 错误处理与重试

### 处理器中的错误处理

```python
@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    try:
        event = request.json
        process_event(event)
        return jsonify({"ok": True}), 200
    
    except ValueError as e:
        # 数据格式错误，不需要重试
        app.logger.error(f"Invalid event data: {e}")
        return jsonify({"error": str(e)}), 400
    
    except ExternalServiceError as e:
        # 外部服务错误，需要重试
        app.logger.error(f"External service error: {e}")
        return jsonify({"error": "retry"}), 500
    
    except Exception as e:
        # 未知错误
        app.logger.exception("Unexpected error")
        return jsonify({"error": "internal"}), 500
```

### 幂等性处理

```python
import redis

redis_client = redis.Redis()

@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    event = request.json
    event_id = event["id"]
    
    # 检查是否已处理
    if redis_client.get(f"webhook:processed:{event_id}"):
        return jsonify({"ok": True, "duplicate": True}), 200
    
    try:
        # 处理事件
        process_event(event)
        
        # 标记为已处理（24小时过期）
        redis_client.setex(
            f"webhook:processed:{event_id}",
            86400,
            "1"
        )
        
        return jsonify({"ok": True}), 200
    
    except Exception as e:
        # 不标记为已处理，允许重试
        raise
```

## 管理 Webhooks

```python
# 列出所有 Webhooks
webhooks = client.webhooks.list()
for wh in webhooks.items:
    print(f"{wh.id}: {wh.url} - {wh.events}")

# 更新 Webhook
webhook = client.webhooks.update(
    webhook_id=webhook.id,
    events=["extraction.completed"],  # 只监听提取完成
    enabled=True
)

# 查看投递历史
deliveries = client.webhooks.deliveries(webhook.id, limit=10)
for d in deliveries.items:
    print(f"{d.id}: {d.event_type} - {d.status}")

# 重新投递
client.webhooks.redeliver(webhook.id, delivery_id)

# 删除 Webhook
client.webhooks.delete(webhook.id)
```

## 下一步

- [批量处理](batch-processing.md) - 结合 Webhook 的批处理
- [多租户配置](../advanced/multi-tenant-setup.md) - 多租户 Webhook 隔离
- [性能调优](../advanced/performance-tuning.md) - 高并发 Webhook 处理
