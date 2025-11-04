"""
队列模块 - Redis 消息队列和 Pub/Sub

提供：
- RedisQueueClient: 队列客户端封装
- 队列常量：QueueNames, EventChannels, TaskStatus 等
- 全局单例访问：get_queue_client()

使用示例：
```python
from unifiles.core.queue import get_queue_client, QueueNames, EventChannels

# 获取队列客户端
queue = get_queue_client()

# 入队任务
await queue.enqueue(QueueNames.FILE_UPLOAD, {
    "task_id": "task_123",
    "file_id": "file_456"
})

# 出队任务
task = await queue.dequeue(QueueNames.FILE_UPLOAD, timeout=10)

# 发布事件
await queue.publish(EventChannels.FILE_UPLOADS, {
    "event": "file_uploaded",
    "file_id": "file_456"
})
```
"""

from unifiles.core.queue.constants import (
    QueueNames,
    EventChannels,
    TaskStatus,
    TaskTypes,
    TaskPriority,
    SemaphoreKeys,
    EventTypes,
    RedisKeyPrefixes,
)

from unifiles.core.queue.redis_queue import (
    RedisQueueClient,
    get_queue_client,
    close_queue_client,
)

__all__ = [
    # 队列客户端
    "RedisQueueClient",
    "get_queue_client",
    "close_queue_client",
    # 常量
    "QueueNames",
    "EventChannels",
    "TaskStatus",
    "TaskTypes",
    "TaskPriority",
    "SemaphoreKeys",
    "EventTypes",
    "RedisKeyPrefixes",
]
