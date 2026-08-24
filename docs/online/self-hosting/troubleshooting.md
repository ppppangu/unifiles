# 故障排除

## 健康检查

```bash
curl http://localhost:8088/health
unifiles --profile local status
```

## 401

确认客户端的 API Key 与 `UNIFILES_BOOTSTRAP_API_KEY` 一致，或使用已有 Key 创建新的 Key。

## 数据目录不可写

```bash
ls -ld "$UNIFILES_DATA_DIR"
```

容器部署时确认 `/data` volume 已挂载且容器用户可写。

## 提取失败

当前内置解析器支持文本和带文本层 PDF。扫描件会明确返回 `EXTRACTION_FAILED`；设置
`UNIFILES_OCR_ENDPOINT`（以及可选的 `UNIFILES_OCR_API_KEY`）后由远程 Provider 处理。
Server 不会伪造 Markdown。

## 查看 API 契约

访问 `http://localhost:8088/docs` 或检查仓库中的 `api/openapi.yaml`。
