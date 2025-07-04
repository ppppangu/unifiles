# /documents/UPLOAD_MINIO_ISSUE_DESIGN.md

问题: 生产环境 Linux 服务器上, 向文件服务器上传文件时, `/upload_minio` 接口完全无法命中 (函数内首行日志也不会打印)。而小数据量 GET/POST 以及 `/process` 接口均正常。

## 1. 现象归纳

1. 对 `/upload_minio` 发起 `POST multipart/form-data` 请求, 客户端立即收到连接被拒或 4xx/5xx, 服务器日志中没有出现 `upload_minio` 内任何 log。
2. 通过浏览器或 Postman 发送 **纯表单** 请求 (无文件) 能够正常进入函数, 说明路由本身可用。
3. 说明问题与 **请求体变大 / multipart 解析** 强相关。

## 2. 可能原因假设

| 编号 | 假设                                                                       | 触发点                           | 理论表现                                |
| ---- | -------------------------------------------------------------------------- | -------------------------------- | --------------------------------------- |
| A    | 反向代理(Nginx/Caddy)`client_max_body_size` 默认 1 MB                      | 请求体大于限制                   | 代理直接返回 413, 后端根本收不到请求    |
| B    | `uvicorn` 本身的 `--limit-max-request-size` 默认 1 MB (0.34.x 以后引入)    | 请求体大于限制                   | Uvicorn 在 HTTP 层返回 413, 不进入 ASGI |
| C    | h11 16 KiB incomplete-event 限制导致 multipart 边界过大                    | 边界字符串 + headers 大于 16 KiB | Uvicorn 返回 400, 服务器未进入路由      |
| D    | 客户端地址拼写成 `/upload_minio/` (多了尾斜杠)                             | 路由严格匹配                     | 404, 函数不执行                         |
| E    | `Expect: 100-continue` handshake被上游吃掉, 客户端在等待 100, 服务器未回应 | 大文件上传常见                   | 请求直接超时, 无日志                    |

## 3. 逐步验证计划

1. **最小化复现**
   ```bash
   curl -v -F "upload_file=@tiny.txt" -F "user_id=test" http://127.0.0.1:8087/upload_minio
   ```

   * 如果返回 404 → 检查 URL 尾斜杠 (假设 D)。
   * 如果返回 413 → 继续第 2 步。
   * 如果没有任何响应直接超时 → 留意 `Expect: 100-continue` (假设 E)。
2. **观察 access log**
   * Uvicorn/NGINX 是否记录到请求路径? 若 Nginx 有而 Uvicorn 无, 则假设 A 成立。
3. **检查 Nginx 配置**
   ```nginx
   server {
       ...
       client_max_body_size 200m;     # 或更大
       proxy_request_buffering off;   # 避免大文件落盘再转发
   }
   ```
4. **确认是否有反向代理**
   如果服务器前面还有 Nginx / Caddy / Traefik 等反向代理, 请在代理层放宽请求体限制, 例如:
   ```nginx
   client_max_body_size 200m;
   proxy_request_buffering off;
   ```

   若直接运行 `uvicorn` 且仍然出现 413, 请查看客户端是否携带 `Expect: 100-continue` 头, 可尝试在 curl 中加上 `-H "Expect:"` 取消该头后再测。
5. **升级到 `httptools` 协议**
   ```bash
   uvicorn main:app --http httptools ...
   ```
6. **增加函数最前置日志**
   ```python
   async def upload_minio(request: Request):
       logger.info("--> enter upload_minio")   # 确认是否进入
       ...
   ```

## 4. 可能的代码层面改进

1. **避免整件读入内存**
   当前:
   ```python
   file_content = await upload_file.read()
   ```

   * 对大文件会占满内存, 建议改为分片写入 MinIO (`upload_file.file` 是 SpooledTemporaryFile)。
2. **请求头、路径提前日志**
   有助于定位是否命中路由。
3. **检测 `python-multipart` 缺失**
   运行时已在 `pyproject.toml` 中声明, 但可在异常捕获中给出更友好的提示。

## 5. 结论 (暂定)

最常见根因是 **反向代理或 ASGI 服务器的请求体大小限制**。待按照上方验证计划执行并确认后, 再决定是否需要修改代码或部署配置。
