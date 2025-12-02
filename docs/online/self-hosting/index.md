# 自部署指南

本指南帮助你在自己的基础设施上部署 Unifiles，实现完全的数据控制和定制化配置。

## 为什么选择自部署？

| 特性 | SaaS 版本 | 自部署版本 |
|------|----------|-----------|
| 数据位置 | 云端托管 | 完全自控 |
| 定制化 | 标准配置 | 完全可定制 |
| 扩展性 | 自动扩展 | 按需配置 |
| 成本 | 按用量付费 | 基础设施成本 |
| 维护 | 零维护 | 需要运维 |
| 合规性 | 通用合规 | 满足特定要求 |

## 部署架构

```
                           ┌─────────────────┐
                           │   负载均衡器     │
                           │  (Nginx/HAProxy) │
                           └────────┬────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │  API 服务  │  │  API 服务  │  │  API 服务  │
              │  (容器)    │  │  (容器)    │  │  (容器)    │
              └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                    │               │               │
         ┌──────────┴───────────────┴───────────────┴──────────┐
         │                                                      │
    ┌────▼────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Redis   │  │  PostgreSQL │  │   MinIO    │  │  Workers   │
    │ (队列)   │  │  (pgvector) │  │  (存储)    │  │  (后台)    │
    └─────────┘  └────────────┘  └────────────┘  └────────────┘
```

## 部署选项

### Docker Compose (推荐入门)

适合单机部署、开发测试或小规模生产环境。

```bash
# 快速启动
git clone https://github.com/your-org/unifiles.git
cd unifiles
docker-compose up -d
```

[查看 Docker Compose 部署指南 →](./docker-compose.md)

### Kubernetes

适合生产环境、需要高可用和自动扩展的场景。

```bash
# 使用 Helm 部署
helm repo add unifiles https://charts.unifiles.io
helm install unifiles unifiles/unifiles
```

[查看 Kubernetes 部署指南 →](./kubernetes.md)

### 云服务商

| 云平台 | 推荐方案 | 文档 |
|--------|---------|------|
| AWS | EKS + RDS + S3 | [AWS 部署指南](#) |
| 阿里云 | ACK + RDS + OSS | [阿里云部署指南](#) |
| 腾讯云 | TKE + TDSQL + COS | [腾讯云部署指南](#) |

## 快速开始

### 1. 检查系统要求

```bash
# 最低配置
CPU: 2 核
内存: 4 GB
存储: 50 GB SSD

# 推荐配置 (生产环境)
CPU: 8 核
内存: 16 GB
存储: 500 GB SSD
```

[查看详细系统要求 →](./requirements.md)

### 2. 准备基础设施

```bash
# 克隆项目
git clone https://github.com/your-org/unifiles.git
cd unifiles

# 复制环境配置
cp .env.example .env

# 编辑配置
vim .env
```

### 3. 启动服务

```bash
# Docker Compose 方式
docker-compose up -d

# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

### 4. 初始化数据库

```bash
# 运行迁移脚本
docker-compose exec api python -m unifiles.scripts.migrate

# 创建管理员账户
docker-compose exec api python -m unifiles.scripts.create_admin
```

### 5. 验证部署

```bash
# 健康检查
curl http://localhost:8088/health

# 测试 API
curl -X POST http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@test.pdf"
```

## 文档目录

### 基础部署

- [系统要求](./requirements.md) - 硬件、软件和网络要求
- [Docker Compose 部署](./docker-compose.md) - 单机部署指南
- [Kubernetes 部署](./kubernetes.md) - 集群部署指南

### 配置管理

- [配置说明](./configuration.md) - 环境变量和配置文件
- [数据库设置](./database-setup.md) - PostgreSQL 和 pgvector 配置
- [存储设置](./storage-setup.md) - MinIO/S3 配置

### 运维管理

- [可观测性](./observability.md) - 日志、指标和追踪
- [备份与恢复](./backup-restore.md) - 数据保护策略
- [升级指南](./upgrade.md) - 版本升级流程
- [故障排除](./troubleshooting.md) - 常见问题解决

## 支持矩阵

### 支持的数据库版本

| 数据库 | 最低版本 | 推荐版本 |
|--------|---------|---------|
| PostgreSQL | 14 | 15+ |
| pgvector | 0.5.0 | 0.6.0+ |
| Redis | 6.0 | 7.0+ |

### 支持的存储后端

| 存储 | 支持状态 |
|------|---------|
| MinIO | 完全支持 |
| AWS S3 | 完全支持 |
| 阿里云 OSS | 完全支持 |
| 腾讯云 COS | 完全支持 |
| 本地文件系统 | 开发环境 |

### 支持的操作系统

| 操作系统 | 支持状态 |
|---------|---------|
| Ubuntu 20.04+ | 完全支持 |
| CentOS 8+ | 完全支持 |
| Debian 11+ | 完全支持 |
| macOS (开发) | 完全支持 |
| Windows (WSL2) | 实验性支持 |

## 获取帮助

- [GitHub Issues](https://github.com/your-org/unifiles/issues) - 报告问题
- [GitHub Discussions](https://github.com/your-org/unifiles/discussions) - 社区讨论
- [故障排除指南](./troubleshooting.md) - 常见问题解决

## 下一步

1. [检查系统要求](./requirements.md)
2. [选择部署方式](./docker-compose.md)
3. [配置服务](./configuration.md)
