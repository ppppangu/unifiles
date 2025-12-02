# 错误码参考

## 错误响应格式

```json
{
    "error": {
        "code": "ERROR_CODE",
        "message": "错误描述",
        "details": {},
        "request_id": "req_xyz789"
    }
}
```

## 认证错误 (401)

| 错误码 | 说明 |
|-------|------|
| `INVALID_API_KEY` | API Key 无效 |
| `EXPIRED_API_KEY` | API Key 已过期 |
| `REVOKED_API_KEY` | API Key 已被撤销 |
| `MISSING_AUTH` | 未提供认证信息 |

## 权限错误 (403)

| 错误码 | 说明 |
|-------|------|
| `INSUFFICIENT_SCOPE` | API Key 权限不足 |
| `RESOURCE_ACCESS_DENIED` | 无权访问该资源 |
| `QUOTA_EXCEEDED` | 配额已用完 |

## 资源错误 (404)

| 错误码 | 说明 |
|-------|------|
| `FILE_NOT_FOUND` | 文件不存在 |
| `EXTRACTION_NOT_FOUND` | 提取任务不存在 |
| `KNOWLEDGE_BASE_NOT_FOUND` | 知识库不存在 |
| `DOCUMENT_NOT_FOUND` | 文档不存在 |
| `WEBHOOK_NOT_FOUND` | Webhook 不存在 |

## 请求错误 (400/422)

| 错误码 | 说明 |
|-------|------|
| `INVALID_REQUEST` | 请求格式错误 |
| `INVALID_PARAMETER` | 参数值无效 |
| `MISSING_PARAMETER` | 缺少必需参数 |
| `INVALID_FILE_TYPE` | 不支持的文件类型 |
| `FILE_TOO_LARGE` | 文件过大 |
| `DUPLICATE_RESOURCE` | 资源已存在 |

## 处理错误 (422)

| 错误码 | 说明 |
|-------|------|
| `UNSUPPORTED_FORMAT` | 不支持的文件格式 |
| `CORRUPTED_FILE` | 文件已损坏 |
| `ENCRYPTED_FILE` | 文件有密码保护 |
| `OCR_FAILED` | OCR 识别失败 |
| `EXTRACTION_TIMEOUT` | 提取超时 |
| `EXTRACTION_NOT_COMPLETED` | 提取未完成 |

## 速率限制 (429)

| 错误码 | 说明 |
|-------|------|
| `RATE_LIMIT_EXCEEDED` | 请求频率超限 |
| `CONCURRENT_LIMIT_EXCEEDED` | 并发请求超限 |

## 服务器错误 (500/503)

| 错误码 | 说明 |
|-------|------|
| `INTERNAL_ERROR` | 内部服务错误 |
| `SERVICE_UNAVAILABLE` | 服务暂时不可用 |
| `DATABASE_ERROR` | 数据库错误 |
| `STORAGE_ERROR` | 存储服务错误 |
