# 系统要求

## Python 安装

- Python 3.11+
- 可写的数据目录
- 文本/PDF 处理所需的 CPU 和磁盘空间

## Docker 安装

- Docker Engine 24+
- Docker Compose v2
- 持久化 volume

单机版本不要求 PostgreSQL、Redis 或 MinIO。生产环境应设置随机
`UNIFILES_BOOTSTRAP_API_KEY`，并通过反向代理启用 HTTPS。

SQLite 单机后端固定使用一个 Server 进程；任务并发由进程内线程池处理。多实例部署需先
实现共享的 PostgreSQL/对象存储/队列适配器。
