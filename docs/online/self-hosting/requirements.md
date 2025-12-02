# 系统要求

本文档详细说明部署 Unifiles 所需的硬件、软件和网络要求。

## 硬件要求

### 最低配置 (开发/测试)

| 组件 | 要求 |
|------|------|
| CPU | 2 核 |
| 内存 | 4 GB |
| 存储 | 50 GB SSD |
| 网络 | 100 Mbps |

### 推荐配置 (小规模生产)

| 组件 | 要求 |
|------|------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 存储 | 200 GB SSD |
| 网络 | 1 Gbps |

### 生产配置 (高可用)

| 组件 | API 服务器 | 数据库服务器 | 存储服务器 |
|------|-----------|-------------|-----------|
| CPU | 8 核 | 8 核 | 4 核 |
| 内存 | 16 GB | 32 GB | 16 GB |
| 存储 | 100 GB SSD | 500 GB NVMe | 2 TB HDD |
| 实例数 | 3+ | 2 (主从) | 4+ (分布式) |

### 容量规划

```
每 10,000 个文档约需:
- PostgreSQL: 1 GB 存储
- pgvector 索引: 2 GB 存储 (1536 维)
- MinIO: 取决于原始文件大小

每 1,000 QPS 约需:
- API 服务器: 2 核 CPU, 4 GB 内存
- Redis: 1 GB 内存
```

## 软件要求

### 操作系统

| 系统 | 版本 | 支持状态 |
|------|------|---------|
| Ubuntu | 20.04 LTS | 完全支持 |
| Ubuntu | 22.04 LTS | 完全支持 (推荐) |
| CentOS | 8+ | 完全支持 |
| Debian | 11+ | 完全支持 |
| macOS | 12+ | 开发环境 |
| Windows | WSL2 | 实验性 |

### 容器运行时

| 运行时 | 版本 | 备注 |
|--------|------|------|
| Docker | 20.10+ | 推荐 |
| containerd | 1.6+ | Kubernetes 环境 |
| Podman | 4.0+ | 可选替代 |

### 数据库

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| PostgreSQL | 14 | 15+ |
| pgvector 扩展 | 0.5.0 | 0.6.0+ |

### 缓存/队列

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Redis | 6.0 | 7.0+ |

### 对象存储

| 组件 | 最低版本 | 备注 |
|------|---------|------|
| MinIO | RELEASE.2023-01-01 | 推荐自部署 |
| AWS S3 | - | 云托管 |
| 兼容 S3 协议 | - | 阿里云 OSS 等 |

### Python 环境 (源码部署)

| 组件 | 版本 |
|------|------|
| Python | 3.11+ |
| pip | 21.0+ |
| uv | 0.1+ (推荐) |

## 网络要求

### 端口配置

| 服务 | 默认端口 | 协议 | 说明 |
|------|---------|------|------|
| API 服务 | 8088 | HTTP/HTTPS | 主 API 端口 |
| PostgreSQL | 5432 | TCP | 数据库连接 |
| Redis | 6379 | TCP | 缓存/队列 |
| MinIO API | 9000 | HTTP | 存储 API |
| MinIO Console | 9001 | HTTP | 管理界面 |

### 防火墙规则

```bash
# 入站规则 (公网)
允许: 80/tcp (HTTP)
允许: 443/tcp (HTTPS)

# 入站规则 (内网)
允许: 8088/tcp (API 服务)
允许: 5432/tcp (PostgreSQL)
允许: 6379/tcp (Redis)
允许: 9000/tcp (MinIO)

# 出站规则
允许: 443/tcp (HTTPS - 调用外部 API)
允许: 53/udp (DNS)
```

### 网络延迟要求

| 组件间 | 最大延迟 | 说明 |
|--------|---------|------|
| API ↔ PostgreSQL | < 5ms | 同一数据中心 |
| API ↔ Redis | < 1ms | 同一数据中心 |
| API ↔ MinIO | < 10ms | 同一区域 |

### 带宽要求

```
文件上传: 取决于用户数和文件大小
文件下载: 取决于用户数和文件大小
内部通信: 1 Gbps+ 推荐

估算公式:
上传带宽 = 并发上传数 × 平均文件大小 / 平均上传时间
```

## 依赖服务

### 必需服务

| 服务 | 用途 | 替代方案 |
|------|------|---------|
| PostgreSQL | 元数据存储 | 无 |
| pgvector | 向量存储 | 无 |
| Redis | 队列/缓存 | 无 |
| 对象存储 | 文件存储 | MinIO/S3/OSS |

### 可选服务

| 服务 | 用途 | 说明 |
|------|------|------|
| OpenTelemetry Collector | 追踪收集 | 可观测性 |
| Prometheus | 指标收集 | 监控 |
| Grafana | 可视化 | 监控 |
| Jaeger | 追踪 UI | 可观测性 |

### 外部 API (可选)

| 服务 | 用途 | 说明 |
|------|------|------|
| OpenAI API | 嵌入生成 | 或其他嵌入服务 |
| OCR 服务 | 文档识别 | 内置或外部 |

## 安全要求

### TLS/SSL

```
要求: 生产环境必须启用 HTTPS
证书: 推荐使用 Let's Encrypt 或企业证书
最低版本: TLS 1.2
推荐版本: TLS 1.3
```

### 密钥管理

```
API 密钥: 最少 32 字符随机字符串
数据库密码: 最少 16 字符，包含大小写和数字
加密密钥: 32 字节 (256 位) Fernet 兼容
JWT 密钥: 最少 32 字符
```

### 访问控制

```
数据库: 仅允许内网访问
Redis: 启用密码认证
MinIO: 使用独立的 access/secret key
SSH: 使用密钥认证，禁用密码登录
```

## 检查清单

### 部署前检查

- [ ] 硬件资源满足要求
- [ ] 操作系统版本兼容
- [ ] Docker/Kubernetes 已安装
- [ ] 网络端口已开放
- [ ] 防火墙规则已配置
- [ ] TLS 证书已准备
- [ ] 密钥已生成

### 安装检查

```bash
# 检查 Docker
docker --version
docker-compose --version

# 检查 PostgreSQL 连接
psql -U postgres -h localhost -c "SELECT version();"

# 检查 Redis 连接
redis-cli ping

# 检查 MinIO 连接
mc alias set local http://localhost:9000 minioadmin minioadmin
mc admin info local
```

### 验证检查

```bash
# API 健康检查
curl http://localhost:8088/health

# 数据库连接测试
curl http://localhost:8088/health/db

# 存储连接测试
curl http://localhost:8088/health/storage
```

## 下一步

满足系统要求后，选择部署方式:

- [Docker Compose 部署](./docker-compose.md) - 单机快速部署
- [Kubernetes 部署](./kubernetes.md) - 集群高可用部署
