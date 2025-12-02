# 备份与恢复

本文档介绍 Unifiles 的数据备份策略和灾难恢复流程。

## 备份概述

### 需要备份的数据

| 数据类型 | 存储位置 | 重要性 | 备份频率 |
|---------|---------|--------|---------|
| 数据库 | PostgreSQL | 关键 | 每日 + 实时 WAL |
| 文件数据 | MinIO/S3 | 关键 | 每日增量 |
| 配置文件 | 文件系统 | 重要 | 每次变更 |
| 密钥/证书 | 密钥管理 | 关键 | 每次变更 |

### 备份策略

```
┌─────────────────────────────────────────────────────────────┐
│                      备份策略                                │
├─────────────────────────────────────────────────────────────┤
│  完整备份: 每周日 02:00                                      │
│  增量备份: 每日 02:00                                        │
│  WAL 归档: 实时 (PostgreSQL)                                 │
│  保留周期: 30 天                                             │
└─────────────────────────────────────────────────────────────┘
```

## PostgreSQL 备份

### 逻辑备份 (pg_dump)

```bash
#!/bin/bash
# backup_postgres.sh

# 配置
BACKUP_DIR="/backups/postgres"
DB_HOST="localhost"
DB_NAME="unifiles"
DB_USER="unifiles"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
  -F c -Z 9 \
  -f "$BACKUP_DIR/unifiles_$DATE.dump"

# 验证备份
if [ $? -eq 0 ]; then
    echo "Backup successful: unifiles_$DATE.dump"
    
    # 计算校验和
    sha256sum "$BACKUP_DIR/unifiles_$DATE.dump" > "$BACKUP_DIR/unifiles_$DATE.dump.sha256"
else
    echo "Backup failed!"
    exit 1
fi

# 清理旧备份
find $BACKUP_DIR -name "unifiles_*.dump" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "unifiles_*.sha256" -mtime +$RETENTION_DAYS -delete

echo "Backup completed"
```

### 物理备份 (pg_basebackup)

```bash
#!/bin/bash
# backup_postgres_base.sh

BACKUP_DIR="/backups/postgres/base"
DATE=$(date +%Y%m%d)

# 完整物理备份
pg_basebackup -h localhost -U replicator \
  -D "$BACKUP_DIR/$DATE" \
  -Ft -z -P \
  --checkpoint=fast \
  --wal-method=stream

echo "Base backup completed: $BACKUP_DIR/$DATE"
```

### WAL 归档配置

```ini
# postgresql.conf
archive_mode = on
archive_command = 'cp %p /backups/postgres/wal/%f'
archive_timeout = 300
```

### PITR (时间点恢复)

```bash
# 恢复到特定时间点
# 1. 停止 PostgreSQL
sudo systemctl stop postgresql

# 2. 清空数据目录
rm -rf /var/lib/postgresql/15/main/*

# 3. 恢复基础备份
tar -xzf /backups/postgres/base/20240115/base.tar.gz -C /var/lib/postgresql/15/main/

# 4. 配置恢复
cat > /var/lib/postgresql/15/main/recovery.signal << EOF
EOF

cat >> /var/lib/postgresql/15/main/postgresql.auto.conf << EOF
restore_command = 'cp /backups/postgres/wal/%f %p'
recovery_target_time = '2024-01-15 14:30:00'
recovery_target_action = 'promote'
EOF

# 5. 启动并恢复
sudo systemctl start postgresql
```

## MinIO/S3 备份

### 使用 mc mirror

```bash
#!/bin/bash
# backup_minio.sh

# 配置
SOURCE_ALIAS="production"
BACKUP_ALIAS="backup"
BUCKETS="unifiles-raw unifiles-processed"
DATE=$(date +%Y%m%d)

# 同步每个 bucket
for bucket in $BUCKETS; do
    echo "Backing up $bucket..."
    
    mc mirror --overwrite \
      $SOURCE_ALIAS/$bucket \
      $BACKUP_ALIAS/backups/$DATE/$bucket
    
    if [ $? -eq 0 ]; then
        echo "$bucket backup successful"
    else
        echo "$bucket backup failed!"
    fi
done

# 清理 30 天前的备份
mc rm --recursive --force --older-than 30d $BACKUP_ALIAS/backups/
```

### 跨区域复制

```bash
# 配置跨区域复制
mc replicate add production/unifiles-raw \
  --remote-bucket backup-region/unifiles-raw \
  --replicate "delete,delete-marker,existing-objects"

# 查看复制状态
mc replicate status production/unifiles-raw
```

### S3 版本控制

```bash
# 启用版本控制
aws s3api put-bucket-versioning \
  --bucket unifiles-raw \
  --versioning-configuration Status=Enabled

# 配置生命周期策略 (保留旧版本 30 天)
cat > lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "cleanup-old-versions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 30
            }
        }
    ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket unifiles-raw \
  --lifecycle-configuration file://lifecycle.json
```

## Redis 备份

### RDB 快照

```bash
# 手动触发快照
redis-cli -a $REDIS_PASSWORD BGSAVE

# 复制 RDB 文件
cp /var/lib/redis/dump.rdb /backups/redis/dump_$(date +%Y%m%d).rdb
```

### 自动备份配置

```ini
# redis.conf
save 900 1      # 900秒内有1次写入则保存
save 300 10     # 300秒内有10次写入则保存
save 60 10000   # 60秒内有10000次写入则保存

dir /var/lib/redis
dbfilename dump.rdb
```

### AOF 持久化

```ini
# redis.conf
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
```

## 自动化备份

### Cron 配置

```bash
# /etc/cron.d/unifiles-backup

# PostgreSQL 每日备份 (02:00)
0 2 * * * root /opt/unifiles/scripts/backup_postgres.sh >> /var/log/unifiles/backup.log 2>&1

# PostgreSQL 完整备份 (每周日 03:00)
0 3 * * 0 root /opt/unifiles/scripts/backup_postgres_base.sh >> /var/log/unifiles/backup.log 2>&1

# MinIO 每日备份 (04:00)
0 4 * * * root /opt/unifiles/scripts/backup_minio.sh >> /var/log/unifiles/backup.log 2>&1

# Redis 每日备份 (05:00)
0 5 * * * root /opt/unifiles/scripts/backup_redis.sh >> /var/log/unifiles/backup.log 2>&1
```

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: unifiles
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:15
              command:
                - /bin/bash
                - -c
                - |
                  pg_dump -h $PG_HOST -U $PG_USER -d $PG_DATABASE \
                    -F c -Z 9 -f /backups/unifiles_$(date +%Y%m%d).dump
              env:
                - name: PG_HOST
                  value: "unifiles-postgresql"
                - name: PG_USER
                  valueFrom:
                    secretKeyRef:
                      name: unifiles-secrets
                      key: PG_USER
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: unifiles-secrets
                      key: PG_PASSWORD
              volumeMounts:
                - name: backup-storage
                  mountPath: /backups
          volumes:
            - name: backup-storage
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
```

## 恢复流程

### PostgreSQL 恢复

```bash
# 1. 停止应用
docker-compose stop api worker-upload worker-extraction

# 2. 恢复数据库
pg_restore -h localhost -U unifiles -d unifiles -c \
  /backups/postgres/unifiles_20240115.dump

# 3. 验证数据
psql -U unifiles -d unifiles -c "SELECT count(*) FROM files;"

# 4. 启动应用
docker-compose start api worker-upload worker-extraction
```

### MinIO 恢复

```bash
# 从备份恢复
mc mirror backup/backups/20240115/unifiles-raw production/unifiles-raw

# 验证
mc ls production/unifiles-raw --summarize
```

### 完整灾难恢复

```bash
#!/bin/bash
# disaster_recovery.sh

# 配置
BACKUP_DATE=$1
BACKUP_DIR="/backups"

echo "Starting disaster recovery from $BACKUP_DATE..."

# 1. 恢复 PostgreSQL
echo "Restoring PostgreSQL..."
psql -U postgres -c "DROP DATABASE IF EXISTS unifiles;"
psql -U postgres -c "CREATE DATABASE unifiles OWNER unifiles;"
pg_restore -U unifiles -d unifiles \
  "$BACKUP_DIR/postgres/unifiles_$BACKUP_DATE.dump"

# 2. 恢复 MinIO 数据
echo "Restoring MinIO data..."
mc mirror --overwrite \
  backup/backups/$BACKUP_DATE/unifiles-raw \
  production/unifiles-raw
mc mirror --overwrite \
  backup/backups/$BACKUP_DATE/unifiles-processed \
  production/unifiles-processed

# 3. 恢复 Redis
echo "Restoring Redis..."
redis-cli -a $REDIS_PASSWORD FLUSHALL
redis-cli -a $REDIS_PASSWORD DEBUG RELOAD

# 4. 验证
echo "Validating recovery..."
curl -f http://localhost:8088/health

echo "Disaster recovery completed!"
```

## 备份验证

### 定期恢复测试

```bash
#!/bin/bash
# test_restore.sh

# 在测试环境恢复并验证
TEST_DB="unifiles_restore_test"

# 创建测试数据库
psql -U postgres -c "DROP DATABASE IF EXISTS $TEST_DB;"
psql -U postgres -c "CREATE DATABASE $TEST_DB;"

# 恢复最新备份
LATEST_BACKUP=$(ls -t /backups/postgres/unifiles_*.dump | head -1)
pg_restore -U postgres -d $TEST_DB "$LATEST_BACKUP"

# 运行验证查询
RESULT=$(psql -U postgres -d $TEST_DB -t -c "
SELECT 
    (SELECT count(*) FROM files) as files,
    (SELECT count(*) FROM knowledge_bases) as kbs,
    (SELECT count(*) FROM chunks) as chunks
")

echo "Restore verification: $RESULT"

# 清理
psql -U postgres -c "DROP DATABASE $TEST_DB;"
```

### 备份监控告警

```yaml
# prometheus-alerts.yml
groups:
  - name: backup
    rules:
      - alert: BackupMissing
        expr: time() - backup_last_success_timestamp > 86400 * 2
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Backup not completed for over 2 days"

      - alert: BackupFailed
        expr: backup_last_status != 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Last backup failed"
```

## 下一步

- [升级指南](./upgrade.md) - 升级前备份策略
- [故障排除](./troubleshooting.md) - 恢复问题排查
- [可观测性](./observability.md) - 备份监控
