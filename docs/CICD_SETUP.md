# CI/CD 配置指南

本文档详细说明如何为 Unifiles 项目配置持续集成和持续部署（CI/CD）。

## 📋 目录

- [概述](#概述)
- [前置要求](#前置要求)
- [配置GitHub Secrets](#配置github-secrets)
- [服务器配置](#服务器配置)
- [测试部署](#测试部署)
- [监控和维护](#监控和维护)
- [故障排除](#故障排除)

## 🎯 概述

我们提供两种部署方式：

### 1. 基础SSH部署（推荐新手）
- **触发条件**: 推送到 `main` 分支
- **部署方式**: 直接在服务器运行Python应用
- **优点**: 配置简单，适合小项目
- **文件**: `.github/workflows/deploy.yml`

### 2. Docker部署（推荐生产环境）
- **Staging**: 推送到 `main` 分支自动部署
- **Production**: 创建版本标签时部署
- **优点**: 环境一致性，支持零停机更新
- **文件**: `.github/workflows/docker-deploy.yml`

## 📋 前置要求

### 服务器要求
- Ubuntu 20.04+ 或 CentOS 8+
- 2GB+ RAM
- 20GB+ 存储空间
- SSH访问权限
- 公网IP地址

### 本地要求
- Git 配置完成
- SSH密钥对已生成
- GitHub仓库推送权限

## ⚙️ 配置GitHub Secrets

### Step 1: 进入仓库设置
```
GitHub仓库 → Settings → Secrets and variables → Actions → New repository secret
```

### Step 2: 添加必要的Secrets

#### 基础SSH部署需要：
| Secret名称 | 说明 | 示例 |
|-----------|------|------|
| `HOST` | 服务器IP地址 | `192.168.1.100` |
| `USERNAME` | SSH用户名 | `ubuntu` |
| `SSH_PRIVATE_KEY` | SSH私钥内容 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `PORT` | SSH端口（可选） | `22` |
| `PROJECT_PATH` | 项目路径（可选） | `/var/www/unifiles` |

#### Docker部署需要：
| Secret名称 | 说明 |
|-----------|------|
| `STAGING_HOST` | 测试服务器IP |
| `STAGING_USERNAME` | 测试服务器SSH用户名 |
| `STAGING_SSH_KEY` | 测试服务器SSH私钥 |
| `STAGING_PORT` | 测试服务器SSH端口（可选） |
| `PROD_HOST` | 生产服务器IP |
| `PROD_USERNAME` | 生产服务器SSH用户名 |
| `PROD_SSH_KEY` | 生产服务器SSH私钥 |
| `PROD_PORT` | 生产服务器SSH端口（可选） |

### Step 3: 生成SSH密钥

如果还没有SSH密钥：

```bash
# 生成新的SSH密钥对
ssh-keygen -t rsa -b 4096 -C "github-actions@your-domain.com"

# 查看公钥（添加到服务器）
cat ~/.ssh/id_rsa.pub

# 查看私钥（添加到GitHub Secrets）
cat ~/.ssh/id_rsa
```

## 🖥️ 服务器配置

### 方式1: 基础SSH部署

#### 1. 初始环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git nginx curl wget

# 安装uv（Python包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### 2. 配置SSH访问

```bash
# 添加GitHub Actions的公钥到服务器
mkdir -p ~/.ssh
echo "你的公钥内容" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

#### 3. 克隆项目并安装依赖

```bash
# 克隆项目
sudo git clone https://github.com/你的用户名/Unifiles.git /var/www/unifiles
cd /var/www/unifiles

# 设置权限
sudo chown -R $USER:$USER /var/www/unifiles

# 安装Python依赖
uv sync

# 复制环境配置
cp .env.example .env
# 编辑 .env 文件配置数据库等信息
nano .env
```

#### 4. 创建系统服务

```bash
# 创建systemd服务文件
sudo nano /etc/systemd/system/unifiles.service
```

**unifiles.service 内容：**
```ini
[Unit]
Description=Unifiles FastAPI Application
After=network.target

[Service]
Type=exec
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/unifiles
Environment=PATH=/var/www/unifiles/.venv/bin
Environment=PYTHONPATH=/var/www/unifiles
ExecStart=/var/www/unifiles/.venv/bin/uvicorn unifiles.app.v1.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 5. 启动服务

```bash
# 重新加载systemd配置
sudo systemctl daemon-reload

# 启用并启动服务
sudo systemctl enable unifiles
sudo systemctl start unifiles

# 检查服务状态
sudo systemctl status unifiles

# 查看日志
journalctl -u unifiles -f
```

#### 6. 配置Nginx反向代理（可选）

```bash
# 创建Nginx配置
sudo nano /etc/nginx/sites-available/unifiles
```

**Nginx配置：**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/unifiles /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 方式2: Docker部署

#### 1. 安装Docker

```bash
# 安装Docker
curl -fsSL https://get.docker.com | sh

# 添加用户到docker组
sudo usermod -aG docker $USER

# 重新登录使权限生效
newgrp docker

# 测试Docker安装
docker run hello-world
```

#### 2. 配置环境文件

```bash
# 创建staging环境配置
cat > .env.staging << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/unifiles_staging
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
DEBUG=True
EOF

# 创建production环境配置
cat > .env.production << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/unifiles_prod
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
DEBUG=False
EOF
```

#### 3. 配置Nginx（可选）

创建适合Docker的Nginx配置，支持动态端口切换。

## 🚀 测试部署

### 1. 测试SSH连接

```bash
# 从本地测试SSH连接
ssh -i ~/.ssh/id_rsa username@your_server_ip

# 测试sudo权限（如果workflow需要）
sudo systemctl status unifiles
```

### 2. 测试自动部署

#### 基础SSH部署测试：
```bash
# 1. 做一个小改动
echo "# Test deployment" >> README.md
git add .
git commit -m "test: trigger deployment"
git push origin main

# 2. 检查GitHub Actions
# 访问：https://github.com/你的用户名/Unifiles/actions
```

#### Docker部署测试：
```bash
# 1. 测试staging部署
git push origin main

# 2. 测试production部署
git tag v0.1.0
git push origin v0.1.0
```

### 3. 验证部署结果

```bash
# SSH到服务器检查
ssh username@your_server

# 检查服务状态
sudo systemctl status unifiles

# 检查应用是否响应
curl http://localhost:8000/health

# 查看最新日志
journalctl -u unifiles -n 20
```

## 📊 监控和维护

### 1. 监控部署状态

- **GitHub Actions页面**: 查看工作流执行状态
- **服务器日志**: `journalctl -u unifiles -f`
- **应用日志**: 应用内部日志系统
- **系统资源**: `htop`, `df -h`, `free -m`

### 2. 常用维护命令

```bash
# 查看服务状态
sudo systemctl status unifiles

# 重启服务
sudo systemctl restart unifiles

# 查看实时日志
journalctl -u unifiles -f

# 手动更新代码
cd /var/www/unifiles
git pull origin main
uv sync
sudo systemctl restart unifiles

# 检查端口占用
sudo netstat -tlnp | grep 8000
```

### 3. 日志管理

```bash
# 限制日志大小
sudo journalctl --vacuum-size=100M
sudo journalctl --vacuum-time=30d

# 配置日志轮转
sudo nano /etc/systemd/journald.conf
# 添加：
# SystemMaxUse=100M
# MaxRetentionSec=30day
```

## 🔧 故障排除

### 1. SSH连接失败

**问题**: `Permission denied (publickey)`

**解决方案**:
```bash
# 检查SSH密钥格式（GitHub Actions需要OpenSSH格式）
ssh-keygen -p -m PEM -f ~/.ssh/id_rsa

# 检查服务器上的authorized_keys
cat ~/.ssh/authorized_keys

# 检查SSH配置
sudo nano /etc/ssh/sshd_config
# 确保：
# PubkeyAuthentication yes
# AuthorizedKeysFile .ssh/authorized_keys

# 重启SSH服务
sudo systemctl restart sshd
```

### 2. 权限问题

**问题**: `sudo: no tty present and no askpass program specified`

**解决方案**:
```bash
# 给GitHub Actions用户sudo免密权限
sudo visudo

# 添加（替换username为实际用户名）：
username ALL=(ALL) NOPASSWD:ALL
```

### 3. 端口被占用

**问题**: `Address already in use`

**解决方案**:
```bash
# 查找占用进程
sudo netstat -tlnp | grep 8000
sudo lsof -i :8000

# 杀死进程
sudo kill -9 PID

# 或者修改应用端口
nano /etc/systemd/system/unifiles.service
# 修改端口号
sudo systemctl daemon-reload
sudo systemctl restart unifiles
```

### 4. 依赖安装失败

**问题**: `uv sync` 失败

**解决方案**:
```bash
# 更新uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 清理缓存
uv cache clean

# 重新安装
rm -rf .venv
uv sync
```

### 5. 数据库连接失败

**问题**: 应用无法连接数据库

**解决方案**:
```bash
# 检查数据库服务
sudo systemctl status postgresql

# 检查网络连接
telnet database_host 5432

# 检查环境变量
cat .env | grep DATABASE_URL

# 测试连接
uv run python -c "import asyncpg; print('DB connection test')"
```

## 💡 最佳实践

### 1. 安全建议

- 使用专用的部署密钥，不要使用个人SSH密钥
- 定期轮换SSH密钥
- 限制SSH访问IP地址
- 使用防火墙限制不必要的端口
- 定期更新系统和依赖

### 2. 性能优化

- 使用Nginx作为反向代理
- 配置SSL/TLS证书
- 启用Gzip压缩
- 配置缓存策略
- 监控系统资源使用

### 3. 备份策略

```bash
# 定期备份代码
git push --all origin

# 定期备份数据库
pg_dump unifiles > backup_$(date +%Y%m%d).sql

# 定期备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz /etc/nginx/ /etc/systemd/system/unifiles.service .env
```

### 4. 版本管理

```bash
# 使用语义化版本号
git tag v1.0.0
git tag v1.0.1
git tag v1.1.0

# 记录重要变更
git log --oneline v1.0.0..v1.1.0
```

## 📚 相关文档

- [DEPLOYMENT.md](./DEPLOYMENT.md) - 详细部署指南
- [README.md](../README.md) - 项目介绍和基础设置
- [PROGRESS.md](../PROGRESS.md) - 开发进度追踪

## 🆘 获取帮助

如果在配置过程中遇到问题：

1. 检查GitHub Actions工作流日志
2. 查看服务器系统日志
3. 参考本文档的故障排除部分
4. 提交Issue到GitHub仓库

---

**最后更新**: 2025-09-16
**维护者**: 项目团队