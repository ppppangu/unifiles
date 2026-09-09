# 配置

Server 使用 `UNIFILES_` 前缀环境变量。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UNIFILES_DATA_DIR` | `.unifiles-data` | SQLite 与文件存储目录 |
| `UNIFILES_BOOTSTRAP_API_KEY` | `<bootstrap-key>` | 首个管理 API Key；生产必须替换 |
| `UNIFILES_CORS_ORIGINS` | 本机开发地址 | 逗号分隔的允许来源 |
| `UNIFILES_MAX_FILE_SIZE_BYTES` | `104857600` | 单文件最大字节数 |
| `UNIFILES_STORAGE_LIMIT_BYTES` | `10737418240` | 用户存储配额 |
| `UNIFILES_EXTRACTION_PAGES_LIMIT` | `100000` | 提取页数配额 |
| `UNIFILES_KNOWLEDGE_BASE_LIMIT` | `1000` | 知识库配额 |
| `UNIFILES_OCR_ENDPOINT` | 未设置 | 图片、扫描件和 advanced 模式使用的 OCR HTTP endpoint |
| `UNIFILES_OCR_API_KEY` | 未设置 | OCR endpoint 的 Bearer token |
| `UNIFILES_OCR_TIMEOUT_SECONDS` | `120` | OCR 请求超时 |

CLI 与 SDK 使用 `UNIFILES_API_KEY`、`UNIFILES_BASE_URL`；这些是客户端变量，不应作为
Server 的 bootstrap 配置混用。

OCR endpoint 接收 multipart `file`、`mode` 和 JSON 字符串 `options`，返回：

```json
{
  "markdown": "# 提取结果",
  "total_pages": 3,
  "metadata": {"provider": "custom"}
}
```

也可使用统一的 `{"success": true, "data": ...}` envelope。
