# CLI

`@wyy/unifiles-cli` 是调用远端 API 的 Unix 风格客户端，不负责启动或管理 Server。

```bash
npm install -g @wyy/unifiles-cli
unifiles --help
```

## Profiles

```bash
printf '%s' "$UNIFILES_API_KEY" | unifiles config set production \
  --base-url https://api.unifiles.dev \
  --api-key-stdin

unifiles config use production
unifiles --profile local files list
```

配置写入 `$XDG_CONFIG_HOME/unifiles/config.toml`，文件权限为 `0600`。优先级为命令行
base URL、环境变量、当前 profile、默认值；API Key 可由 `UNIFILES_API_KEY` 覆盖。

## Unix I/O

- TTY 默认表格，管道默认 JSONL。
- `--output table|json|jsonl|raw` 可显式选择。
- stdout 只输出数据，进度和错误写到 stderr。
- `files upload - --filename name.pdf` 从 stdin 上传。
- `files download ID -o -` 将原始字节写到 stdout。
- 删除和撤销命令直接执行，不弹出确认。

## 命令组

```text
unifiles files upload|list|get|download|delete|types
unifiles extractions create|get|list
unifiles kb create|list|get|update|delete|search|hybrid-search
unifiles kb documents add|list|get|delete
unifiles webhooks create|list|get|update|delete
unifiles api-keys create|list|revoke
unifiles usage stats|limits
```
