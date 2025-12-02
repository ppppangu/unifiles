# 存储设置

本文档详细介绍 MinIO 和 S3 兼容存储的安装、配置和优化。

## MinIO 安装

### Docker 方式 (推荐)

#### 单节点模式

```bash
docker run -d \
  --name unifiles-minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=unifiles \
  -e MINIO_ROOT_PASSWORD=your_secure_password \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

#### 分布式模式 (生产推荐)

```yaml
# docker-compose-minio.yml
version: '3.8'

services:
  minio1:
    image: minio/minio:latest
    hostname: minio1
    volumes:
      - minio1_data:/data
    environment:
      MINIO_ROOT_USER: unifiles
      MINIO_ROOT_PASSWORD: your_secure_password
    command: server http://minio{1...4}/data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  minio2:
    image: minio/minio:latest
    hostname: minio2
    volumes:
      - minio2_data:/data
    environment:
      MINIO_ROOT_USER: unifiles
      MINIO_ROOT_PASSWORD: your_secure_password
    command: server http://minio{1...4}/data --console-address ":9001"

  minio3:
    image: minio/minio:latest
    hostname: minio3
    volumes:
      - minio3_data:/data
    environment:
      MINIO_ROOT_USER: unifiles
      MINIO_ROOT_PASSWORD: your_secure_password
    command: server http://minio{1...4}/data --console-address ":9001"

  minio4:
    image: minio/minio:latest
    hostname: minio4
    volumes:
      - minio4_data:/data
    environment:
      MINIO_ROOT_USER: unifiles
      MINIO_ROOT_PASSWORD: your_secure_password
    command: server http://minio{1...4}/data --console-address ":9001"

  nginx:
    image: nginx:alpine
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - ./nginx-minio.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - minio1
      - minio2
      - minio3
      - minio4

volumes:
  minio1_data:
  minio2_data:
  minio3_data:
  minio4_data:
```

负载均衡配置:

```nginx
# nginx-minio.conf
events {
    worker_connections 1024;
}

http {
    upstream minio_api {
        server minio1:9000;
        server minio2:9000;
        server minio3:9000;
        server minio4:9000;
    }

    upstream minio_console {
        server minio1:9001;
        server minio2:9001;
        server minio3:9001;
        server minio4:9001;
    }

    server {
        listen 9000;
        server_name _;

        client_max_body_size 1G;

        location / {
            proxy_pass http://minio_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    server {
        listen 9001;
        server_name _;

        location / {
            proxy_pass http://minio_console;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

### 手动安装

#### Linux

```bash
# 下载 MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/

# 创建数据目录
sudo mkdir -p /data/minio
sudo chown -R minio:minio /data/minio

# 创建 systemd 服务
sudo tee /etc/systemd/system/minio.service << EOF
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target

[Service]
User=minio
Group=minio
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server \$MINIO_OPTS
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 配置环境变量
sudo tee /etc/default/minio << EOF
MINIO_ROOT_USER=unifiles
MINIO_ROOT_PASSWORD=your_secure_password
MINIO_OPTS="/data/minio --console-address :9001"
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable minio
sudo systemctl start minio
```

## Bucket 初始化

### 使用 MinIO Client (mc)

```bash
# 安装 mc
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# 配置别名
mc alias set unifiles http://localhost:9000 unifiles your_secure_password

# 创建 Bucket
mc mb unifiles/unifiles-raw
mc mb unifiles/unifiles-processed
mc mb unifiles/unifiles-cache
mc mb unifiles/unifiles-exports

# 设置 Bucket 策略
mc anonymous set none unifiles/unifiles-raw
mc anonymous set none unifiles/unifiles-processed
mc anonymous set download unifiles/unifiles-exports
```

### 使用 Python

```python
from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="unifiles",
    secret_key="your_secure_password",
    secure=False
)

# 创建 Bucket
buckets = [
    "unifiles-raw",
    "unifiles-processed",
    "unifiles-cache",
    "unifiles-exports"
]

for bucket in buckets:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"Created bucket: {bucket}")
```

## 生命周期策略

### 配置自动清理

```json
// lifecycle.json
{
    "Rules": [
        {
            "ID": "cleanup-cache",
            "Status": "Enabled",
            "Filter": {
                "Prefix": ""
            },
            "Expiration": {
                "Days": 1
            }
        }
    ]
}
```

应用策略:

```bash
# 对 cache bucket 应用生命周期策略
mc ilm import unifiles/unifiles-cache < lifecycle.json

# 查看策略
mc ilm ls unifiles/unifiles-cache

# 导出过期策略
cat > exports_lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "cleanup-exports",
            "Status": "Enabled",
            "Expiration": {
                "Days": 7
            }
        }
    ]
}
EOF

mc ilm import unifiles/unifiles-exports < exports_lifecycle.json
```

## AWS S3 配置

如果使用 AWS S3 替代 MinIO:

### 创建 IAM 策略

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::unifiles-*",
                "arn:aws:s3:::unifiles-*/*"
            ]
        }
    ]
}
```

### 环境变量配置

```bash
# S3 配置
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=AKIAXXXXXXXXXXXXXXXX
MINIO_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MINIO_SECURE=true
MINIO_REGION=ap-northeast-1
```

### 创建 S3 Bucket

```bash
aws s3 mb s3://unifiles-raw --region ap-northeast-1
aws s3 mb s3://unifiles-processed --region ap-northeast-1
aws s3 mb s3://unifiles-cache --region ap-northeast-1
aws s3 mb s3://unifiles-exports --region ap-northeast-1

# 配置生命周期
aws s3api put-bucket-lifecycle-configuration \
  --bucket unifiles-cache \
  --lifecycle-configuration file://cache_lifecycle.json
```

## 阿里云 OSS 配置

### 环境变量

```bash
MINIO_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
MINIO_ACCESS_KEY=LTAI5tXXXXXXXXXXXXXX
MINIO_SECRET_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
MINIO_SECURE=true
MINIO_REGION=cn-hangzhou
```

### 创建 Bucket

```bash
# 使用 ossutil
ossutil mb oss://unifiles-raw --region cn-hangzhou
ossutil mb oss://unifiles-processed --region cn-hangzhou
```

## 性能优化

### MinIO 配置优化

```bash
# 设置并行上传
mc admin config set unifiles api requests_max=100
mc admin config set unifiles api requests_deadline=10s

# 设置压缩
mc admin config set unifiles compression \
  enable=on \
  extensions=".txt,.log,.csv,.json,.md" \
  mime_types="text/*,application/json"

# 重启生效
mc admin service restart unifiles
```

### 缓存配置

```bash
# 配置磁盘缓存
mc admin config set unifiles cache \
  drives=/mnt/cache \
  expiry=90 \
  quota=80

mc admin service restart unifiles
```

### 网络优化

```ini
# /etc/sysctl.conf

# 增加 TCP 缓冲区
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# 增加连接队列
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
```

应用配置:

```bash
sudo sysctl -p
```

## 安全配置

### TLS 配置

```bash
# 创建证书目录
mkdir -p ~/.minio/certs

# 复制证书
cp public.crt ~/.minio/certs/
cp private.key ~/.minio/certs/

# MinIO 会自动使用 HTTPS
```

### 访问策略

```json
// readonly-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::unifiles-exports/*"]
        }
    ]
}
```

创建只读用户:

```bash
mc admin user add unifiles readonly-user readonly-password
mc admin policy create unifiles readonly readonly-policy.json
mc admin policy attach unifiles readonly --user readonly-user
```

### 服务账号

```bash
# 为应用创建专用服务账号
mc admin user svcacct add unifiles unifiles \
  --access-key app-access-key \
  --secret-key app-secret-key \
  --policy app-policy.json
```

## 监控

### 健康检查

```bash
# 检查集群状态
mc admin info unifiles

# 检查磁盘使用
mc admin info unifiles --json | jq '.info.backend'

# 检查 Bucket 大小
mc du unifiles/unifiles-raw
mc du unifiles/unifiles-processed
```

### Prometheus 指标

```bash
# 启用 Prometheus 指标
mc admin prometheus generate unifiles

# 访问指标
curl http://localhost:9000/minio/v2/metrics/cluster
```

### 告警规则

```yaml
# prometheus-rules.yml
groups:
  - name: minio
    rules:
      - alert: MinIODiskSpaceLow
        expr: minio_disk_storage_free_bytes / minio_disk_storage_total_bytes < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MinIO disk space low"
          
      - alert: MinIONodeOffline
        expr: minio_cluster_nodes_offline_total > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "MinIO node offline"
```

## 故障排除

### 连接问题

```bash
# 测试连接
mc admin info unifiles

# 检查服务状态
systemctl status minio

# 查看日志
journalctl -u minio -f
```

### 性能问题

```bash
# 检查 I/O 性能
mc admin speedtest unifiles

# 检查网络延迟
mc admin trace unifiles -v

# 检查磁盘健康
mc admin heal unifiles
```

### 数据恢复

```bash
# 检查数据完整性
mc admin heal unifiles/unifiles-raw --recursive

# 从备份恢复
mc mirror backup-server/unifiles-raw unifiles/unifiles-raw
```

## 下一步

- [可观测性](./observability.md) - 存储监控配置
- [备份与恢复](./backup-restore.md) - 存储备份策略
- [配置说明](./configuration.md) - 完整配置参考
