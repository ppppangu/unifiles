"""
队列名称和事件类型常量

集中管理所有队列名称，确保一致性和可维护性
"""

# ===== 任务队列 =====
class QueueNames:
    """任务队列名称常量"""

    # 文件上传队列
    FILE_UPLOAD = "unifiles:queue:file_upload"

    # 文件处理队列（OCR、AI 提取等）
    FILE_PROCESS = "unifiles:queue:file_process"

    # 高优先级文件处理队列（付费用户、VIP）
    FILE_PROCESS_PRIORITY = "unifiles:queue:file_process:priority"

    # Webhook 发送队列
    WEBHOOK_DISPATCH = "unifiles:queue:webhook_dispatch"

    # 通知队列（邮件、短信等）
    NOTIFICATION = "unifiles:queue:notification"

    # 后台任务队列（清理、定时任务等）
    BACKGROUND_TASK = "unifiles:queue:background_task"


# ===== Pub/Sub 事件频道 =====
class EventChannels:
    """实时事件频道常量"""

    # 用户活动事件（登录、上传、删除等）
    USER_ACTIVITIES = "unifiles:events:user_activities"

    # 文件上传事件
    FILE_UPLOADS = "unifiles:events:file_uploads"

    # 文件处理事件
    FILE_PROCESSING = "unifiles:events:file_processing"

    # 系统指标事件（每 10 秒发布一次）
    SYSTEM_METRICS = "unifiles:events:system_metrics"

    # 管理员告警事件
    ADMIN_ALERTS = "unifiles:events:admin_alerts"

    # 配额告警事件
    QUOTA_ALERTS = "unifiles:events:quota_alerts"


# ===== 任务状态 =====
class TaskStatus:
    """任务状态常量"""

    QUEUED = "queued"  # 已入队，等待处理
    PROCESSING = "processing"  # 正在处理
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败
    CANCELLED = "cancelled"  # 已取消
    RETRY = "retry"  # 重试中


# ===== 任务类型 =====
class TaskTypes:
    """任务类型常量"""

    # 文件上传
    FILE_UPLOAD = "file_upload"

    # 文件处理
    FILE_PROCESS_OCR = "file_process_ocr"
    FILE_PROCESS_AI_EXTRACTION = "file_process_ai_extraction"
    FILE_PROCESS_THUMBNAIL = "file_process_thumbnail"
    FILE_PROCESS_CONVERT = "file_process_convert"

    # Webhook
    WEBHOOK_DISPATCH = "webhook_dispatch"

    # 通知
    NOTIFICATION_EMAIL = "notification_email"
    NOTIFICATION_SMS = "notification_sms"

    # 后台任务
    BACKGROUND_CLEANUP = "background_cleanup"
    BACKGROUND_METRICS = "background_metrics"


# ===== 信号量名称 =====
class SemaphoreKeys:
    """信号量键名常量（用于并发控制）"""

    # OCR 处理并发控制
    OCR_WORKERS = "unifiles:semaphore:ocr_workers"

    # AI 提取并发控制
    AI_EXTRACTION_WORKERS = "unifiles:semaphore:ai_extraction_workers"

    # 文件上传并发控制
    UPLOAD_WORKERS = "unifiles:semaphore:upload_workers"

    # Webhook 发送并发控制
    WEBHOOK_WORKERS = "unifiles:semaphore:webhook_workers"


# ===== 事件类型 =====
class EventTypes:
    """事件类型常量（用于 Pub/Sub 和 Webhook）"""

    # 文件事件
    FILE_UPLOADED = "file.uploaded"
    FILE_PROCESSED = "file.processed"
    FILE_DELETED = "file.deleted"
    FILE_SHARED = "file.shared"

    # 用户事件
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # 订阅事件
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"

    # 配额事件
    QUOTA_WARNING = "quota.warning"
    QUOTA_EXCEEDED = "quota.exceeded"

    # 系统事件
    SYSTEM_ERROR = "system.error"
    SYSTEM_ALERT = "system.alert"


# ===== 优先级 =====
class TaskPriority:
    """任务优先级常量"""

    LOW = 0  # 低优先级
    NORMAL = 10  # 普通优先级
    HIGH = 50  # 高优先级（付费用户）
    URGENT = 100  # 紧急优先级（VIP、管理员）


# ===== Redis 键前缀 =====
class RedisKeyPrefixes:
    """Redis 键前缀常量"""

    # 任务状态
    TASK_STATUS = "unifiles:task:status:"

    # 任务元数据
    TASK_METADATA = "unifiles:task:metadata:"

    # 任务锁（防止重复处理）
    TASK_LOCK = "unifiles:task:lock:"

    # 用户配额缓存
    USER_QUOTA = "unifiles:quota:user:"

    # Token 缓存
    TOKEN_CACHE = "unifiles:cache:token:"

    # 速率限制
    RATE_LIMIT = "unifiles:ratelimit:"
