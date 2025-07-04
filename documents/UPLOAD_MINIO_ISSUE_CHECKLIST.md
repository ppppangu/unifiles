# /documents/UPLOAD_MINIO_ISSUE_CHECKLIST.md
| 序号 | 任务                                                          | 负责人                                           | 状态        |
| ---- | ------------------------------------------------------------- | ------------------------------------------------ | ----------- |
| 1    | 使用 `curl` 发送小文件, 记录响应状态                          | 已完成，同一局域网直连 127.0.0.1/192.168.* 成功  | DONE        |
| 2    | 收集 Nginx / Uvicorn access log, 判断是否路由命中             | 局域网直连 uvicorn 已确认命中，cpolar 方向待验证 | IN PROGRESS |
| 3    | 如返回 413, 在 Nginx 中设置 `client_max_body_size 200m`       |                                                  | TODO        |
| 4    | 检查并放宽反向代理(Nginx/Caddy) `client_max_body_size` 等限制 |                                                  | TODO        |
| 5    | 若仍失败, 启用 `--http httptools` 并观察行为                  |                                                  | TODO        |
| 6    | 在 `upload_minio` 首行加入进入日志, 再次测试                  |                                                  | TODO        |
| 7    | 确认可成功上传 ≥ 50 MB 文件                                   |                                                  | TODO        |
| 8    | 评估并实施分片上传以降低内存占用                              |                                                  | TODO        |
| 9    | 更新文档, 关闭 checklist                                      |                                                  | TODO        |