# 升级指南

本文档介绍如何安全地升级 Unifiles 到新版本。

## 升级前准备

### 1. 查看版本说明

```bash
# 查看当前版本
curl http://localhost:8088/health | jq '.version'

# 查看目标版本的 Release Notes
# https://github.com/your-org/unifiles/releases
```

### 2. 检查兼容性

| 升级路径 | 支持 | 说明 |
|---------|------|------|
| 1.x → 1.x+1 | 直接升级 | 小版本升级 |
| 1.x → 1.x+n | 逐步升级 | 跳版本需逐步 |
| 1.x → 2.x | 迁移升级 | 需要数据迁移 |

### 3. 备份数据

```bash
# 执行完整备份
./scripts/backup_all.sh

# 验证备份
ls -la /backups/
```

### 4. 检查磁盘空间

```bash
# 确保有足够空间
df -h

# 预留空间: 当前数据量的 2 倍
```

### 5. 通知用户

```bash
# 设置维护模式
curl -X POST http://localhost:8088/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"enabled": true, "message": "系统升级中，预计 30 分钟"}'
```

## Docker Compose 升级

### 小版本升级 (1.x.y → 1.x.z)

```bash
# 1. 拉取新镜像
docker-compose pull

# 2. 滚动重启 (零停机)
docker-compose up -d --no-deps api
docker-compose up -d --no-deps worker-upload
docker-compose up -d --no-deps worker-extraction

# 3. 验证
curl http://localhost:8088/health
```

### 中版本升级 (1.x → 1.y)

```bash
# 1. 备份
./scripts/backup_all.sh

# 2. 停止服务
docker-compose down

# 3. 更新配置文件 (如有变化)
vim docker-compose.yml
vim .env

# 4. 拉取新镜像
docker-compose pull

# 5. 运行数据迁移
docker-compose run --rm api python -m unifiles.scripts.migrate

# 6. 启动服务
docker-compose up -d

# 7. 验证
docker-compose ps
curl http://localhost:8088/health
```

### 大版本升级 (1.x → 2.x)

```bash
# 1. 完整备份
./scripts/backup_all.sh
./scripts/backup_config.sh

# 2. 停止服务
docker-compose down

# 3. 保存旧配置
cp docker-compose.yml docker-compose.yml.v1
cp .env .env.v1

# 4. 获取新版本配置
curl -O https://raw.githubusercontent.com/your-org/unifiles/v2.0.0/docker-compose.yml
curl -O https://raw.githubusercontent.com/your-org/unifiles/v2.0.0/.env.example

# 5. 迁移配置
./scripts/migrate_config.sh .env.v1 .env

# 6. 拉取新镜像
docker-compose pull

# 7. 运行数据迁移
docker-compose run --rm api python -m unifiles.scripts.migrate --from-version 1.x

# 8. 启动服务
docker-compose up -d

# 9. 验证
./scripts/verify_upgrade.sh
```

## Kubernetes 升级

### 使用 Helm

```bash
# 1. 备份当前 values
helm get values unifiles -n unifiles > values-backup.yaml

# 2. 查看可用版本
helm search repo unifiles --versions

# 3. 查看升级变更
helm diff upgrade unifiles unifiles/unifiles \
  -n unifiles \
  --version 2.0.0 \
  -f values.yaml

# 4. 执行升级
helm upgrade unifiles unifiles/unifiles \
  -n unifiles \
  --version 2.0.0 \
  -f values.yaml \
  --wait \
  --timeout 10m

# 5. 验证
kubectl get pods -n unifiles
kubectl rollout status deployment/unifiles-api -n unifiles
```

### 回滚

```bash
# 查看历史版本
helm history unifiles -n unifiles

# 回滚到上一版本
helm rollback unifiles -n unifiles

# 回滚到指定版本
helm rollback unifiles 3 -n unifiles
```

### 金丝雀发布

```bash
# 1. 部署新版本 (10% 流量)
helm upgrade unifiles unifiles/unifiles \
  -n unifiles \
  --set api.image.tag=2.0.0 \
  --set api.canary.enabled=true \
  --set api.canary.weight=10

# 2. 监控新版本
kubectl logs -n unifiles -l app=unifiles-api,version=2.0.0 -f

# 3. 逐步增加流量
helm upgrade unifiles unifiles/unifiles \
  -n unifiles \
  --set api.canary.weight=50

# 4. 完成升级
helm upgrade unifiles unifiles/unifiles \
  -n unifiles \
  --set api.image.tag=2.0.0 \
  --set api.canary.enabled=false
```

## 数据库迁移

### 查看待执行迁移

```bash
# 列出待执行的迁移
python -m unifiles.scripts.migrate --list

# 输出示例:
# Pending migrations:
# - 042_add_document_title.sql
# - 043_add_chunk_metadata_index.sql
```

### 执行迁移

```bash
# 执行所有待执行的迁移
python -m unifiles.scripts.migrate

# 执行到指定版本
python -m unifiles.scripts.migrate --target 042

# 试运行 (不实际执行)
python -m unifiles.scripts.migrate --dry-run
```

### 迁移回滚

```bash
# 回滚最后一次迁移
python -m unifiles.scripts.migrate --rollback

# 回滚到指定版本
python -m unifiles.scripts.migrate --rollback-to 041
```

### 手动迁移

对于复杂迁移，可能需要手动执行:

```bash
# 1. 连接数据库
psql -U unifiles -d unifiles

# 2. 执行迁移 SQL
\i /path/to/migration.sql

# 3. 记录迁移状态
INSERT INTO schema_migrations (version, applied_at) 
VALUES ('042', NOW());
```

## 升级验证

### 自动验证脚本

```bash
#!/bin/bash
# verify_upgrade.sh

echo "=== Unifiles Upgrade Verification ==="

# 1. 检查服务状态
echo "Checking service health..."
HEALTH=$(curl -s http://localhost:8088/health)
if [ "$(echo $HEALTH | jq -r '.status')" != "healthy" ]; then
    echo "FAILED: Service unhealthy"
    exit 1
fi
echo "OK: Service is healthy"

# 2. 检查版本
echo "Checking version..."
VERSION=$(echo $HEALTH | jq -r '.version')
echo "Current version: $VERSION"

# 3. 检查数据库连接
echo "Checking database..."
DB_STATUS=$(curl -s http://localhost:8088/health/detailed | jq -r '.components.database.status')
if [ "$DB_STATUS" != "healthy" ]; then
    echo "FAILED: Database unhealthy"
    exit 1
fi
echo "OK: Database is healthy"

# 4. 检查存储连接
echo "Checking storage..."
STORAGE_STATUS=$(curl -s http://localhost:8088/health/detailed | jq -r '.components.storage.status')
if [ "$STORAGE_STATUS" != "healthy" ]; then
    echo "FAILED: Storage unhealthy"
    exit 1
fi
echo "OK: Storage is healthy"

# 5. 运行集成测试
echo "Running integration tests..."
python -m pytest tests/integration -v --tb=short
if [ $? -ne 0 ]; then
    echo "FAILED: Integration tests failed"
    exit 1
fi
echo "OK: Integration tests passed"

# 6. 检查关键功能
echo "Checking critical functions..."

# 测试文件上传
UPLOAD_RESULT=$(curl -s -X POST http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer $TEST_API_KEY" \
  -F "file=@test/fixtures/test.pdf")
if [ "$(echo $UPLOAD_RESULT | jq -r '.success')" != "true" ]; then
    echo "FAILED: File upload failed"
    exit 1
fi
echo "OK: File upload working"

echo "=== Verification Completed Successfully ==="
```

### 手动验证清单

- [ ] 服务健康检查通过
- [ ] 版本号正确
- [ ] 数据库连接正常
- [ ] 存储连接正常
- [ ] 文件上传功能正常
- [ ] 内容提取功能正常
- [ ] 知识库搜索功能正常
- [ ] API 响应时间正常
- [ ] 日志无异常错误
- [ ] 队列处理正常

## 故障回滚

### Docker Compose 回滚

```bash
# 1. 停止服务
docker-compose down

# 2. 恢复旧版本镜像
docker tag unifiles/api:latest unifiles/api:failed
docker pull unifiles/api:1.0.0
docker tag unifiles/api:1.0.0 unifiles/api:latest

# 3. 恢复数据库 (如果已迁移)
pg_restore -U unifiles -d unifiles -c /backups/postgres/pre_upgrade.dump

# 4. 恢复配置
cp docker-compose.yml.backup docker-compose.yml
cp .env.backup .env

# 5. 启动旧版本
docker-compose up -d
```

### Kubernetes 回滚

```bash
# Helm 回滚
helm rollback unifiles -n unifiles

# 或手动回滚 Deployment
kubectl rollout undo deployment/unifiles-api -n unifiles
```

## 升级最佳实践

### 升级窗口选择

- 选择业务低峰期
- 预留足够的升级和验证时间
- 确保有团队成员值守

### 通信模板

```
主题: [维护通知] Unifiles 系统升级

尊敬的用户:

我们计划于 2024-01-20 02:00-04:00 (UTC+8) 进行系统升级。

升级内容:
- 版本: 1.5.0 → 2.0.0
- 新功能: XXX
- 性能优化: XXX

影响:
- 升级期间服务将暂时不可用
- 预计停机时间: 30 分钟

如有问题，请联系 support@example.com

谢谢您的理解与支持！
```

### 升级清单

```markdown
## 升级前
- [ ] 阅读 Release Notes
- [ ] 检查兼容性
- [ ] 备份数据
- [ ] 通知用户
- [ ] 准备回滚方案

## 升级中
- [ ] 启用维护模式
- [ ] 执行升级步骤
- [ ] 运行数据迁移
- [ ] 验证服务状态

## 升级后
- [ ] 运行验证脚本
- [ ] 监控错误日志
- [ ] 监控性能指标
- [ ] 关闭维护模式
- [ ] 通知用户完成
```

## 下一步

- [故障排除](./troubleshooting.md) - 升级问题排查
- [备份与恢复](./backup-restore.md) - 回滚数据恢复
- [可观测性](./observability.md) - 监控升级过程
