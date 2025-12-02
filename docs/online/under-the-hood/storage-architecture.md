# 存储架构

本文档详细介绍 Unifiles 的对象存储系统设计，包括 MinIO 配置、存储策略和数据组织方式。

## 存储技术栈

```
MinIO (S3 兼容)
├── 原始文件存储 (Layer 1)
├── 转换后文件缓存
├── 临时处理文件
└── 备份与归档
```

## 存储层级

### Bucket 组织结构

```
unifiles-storage/
├── raw/                    # 原始上传文件
│   └── {user_id}/
│       └── {file_id}/
│           └── {filename}
│
├── processed/              # 处理后文件
│   └── {user_id}/
│       └── {file_id}/
│           ├── converted.pdf
│           ├── pages/
│           │   ├── page_001.png
│           │   └── page_002.png
│           └── ocr_result.json
│
├── cache/                  # 临时缓存
│   └── {date}/
│       └── {task_id}/
│
└── exports/                # 导出文件
    └── {user_id}/
        └── {export_id}/
```

### 存储键命名规范

```python
# 原始文件
raw/{user_id}/{file_id}/{original_filename}

# 转换后 PDF
processed/{user_id}/{file_id}/converted.pdf

# 页面图片
processed/{user_id}/{file_id}/pages/page_{page_num:03d}.png

# OCR 结果
processed/{user_id}/{file_id}/ocr_result.json

# 缓存文件 (24小时过期)
cache/{date}/{task_id}/{filename}

# 导出文件
exports/{user_id}/{export_id}/{filename}
```

## MinIO 配置

### 基础配置

```yaml
# docker-compose.yml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
      MINIO_REGION: us-east-1
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"   # API
      - "9001:9001"   # Console
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
```

### 环境变量

```bash
# MinIO 连接配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false  # 生产环境设为 true
MINIO_REGION=us-east-1

# Bucket 名称
MINIO_BUCKET_RAW=unifiles-raw
MINIO_BUCKET_PROCESSED=unifiles-processed
MINIO_BUCKET_CACHE=unifiles-cache
MINIO_BUCKET_EXPORTS=unifiles-exports
```

### Bucket 策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": ["*"]},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::unifiles-exports/*"],
      "Condition": {
        "StringEquals": {
          "s3:ExistingObjectTag/public": "true"
        }
      }
    }
  ]
}
```

## 存储服务实现

### StorageService 接口

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from dataclasses import dataclass

@dataclass
class StorageObject:
    key: str
    size: int
    content_type: str
    etag: str
    last_modified: datetime
    metadata: dict

class StorageService(ABC):
    """存储服务抽象接口"""
    
    @abstractmethod
    async def upload(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        content_type: str,
        metadata: Optional[dict] = None
    ) -> str:
        """上传文件，返回 ETag"""
        pass
    
    @abstractmethod
    async def download(
        self,
        bucket: str,
        key: str
    ) -> bytes:
        """下载文件内容"""
        pass
    
    @abstractmethod
    async def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires: int = 3600,
        method: str = "GET"
    ) -> str:
        """生成预签名 URL"""
        pass
    
    @abstractmethod
    async def delete(
        self,
        bucket: str,
        key: str
    ) -> bool:
        """删除文件"""
        pass
    
    @abstractmethod
    async def exists(
        self,
        bucket: str,
        key: str
    ) -> bool:
        """检查文件是否存在"""
        pass
    
    @abstractmethod
    async def list_objects(
        self,
        bucket: str,
        prefix: str,
        max_keys: int = 1000
    ) -> list[StorageObject]:
        """列出对象"""
        pass
```

### MinIO 实现

```python
from minio import Minio
from minio.error import S3Error
import asyncio
from functools import partial

class MinIOStorageService(StorageService):
    """MinIO 存储服务实现"""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: str = "us-east-1"
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region
        )
        self._loop = asyncio.get_event_loop()
    
    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步方法"""
        return await self._loop.run_in_executor(
            None,
            partial(func, *args, **kwargs)
        )
    
    async def upload(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        content_type: str,
        metadata: Optional[dict] = None
    ) -> str:
        # 确保 bucket 存在
        if not await self._run_sync(self.client.bucket_exists, bucket):
            await self._run_sync(self.client.make_bucket, bucket)
        
        # 获取文件大小
        data.seek(0, 2)
        size = data.tell()
        data.seek(0)
        
        # 上传文件
        result = await self._run_sync(
            self.client.put_object,
            bucket,
            key,
            data,
            size,
            content_type=content_type,
            metadata=metadata or {}
        )
        
        return result.etag
    
    async def download(self, bucket: str, key: str) -> bytes:
        response = await self._run_sync(
            self.client.get_object,
            bucket,
            key
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    
    async def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires: int = 3600,
        method: str = "GET"
    ) -> str:
        from datetime import timedelta
        
        if method == "GET":
            return await self._run_sync(
                self.client.presigned_get_object,
                bucket,
                key,
                expires=timedelta(seconds=expires)
            )
        elif method == "PUT":
            return await self._run_sync(
                self.client.presigned_put_object,
                bucket,
                key,
                expires=timedelta(seconds=expires)
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
    
    async def delete(self, bucket: str, key: str) -> bool:
        try:
            await self._run_sync(
                self.client.remove_object,
                bucket,
                key
            )
            return True
        except S3Error:
            return False
    
    async def exists(self, bucket: str, key: str) -> bool:
        try:
            await self._run_sync(
                self.client.stat_object,
                bucket,
                key
            )
            return True
        except S3Error:
            return False
    
    async def list_objects(
        self,
        bucket: str,
        prefix: str,
        max_keys: int = 1000
    ) -> list[StorageObject]:
        objects = []
        
        result = await self._run_sync(
            self.client.list_objects,
            bucket,
            prefix=prefix,
            recursive=True
        )
        
        for obj in result:
            if len(objects) >= max_keys:
                break
            objects.append(StorageObject(
                key=obj.object_name,
                size=obj.size,
                content_type=obj.content_type or "application/octet-stream",
                etag=obj.etag,
                last_modified=obj.last_modified,
                metadata={}
            ))
        
        return objects
```

### 工厂模式

```python
from enum import Enum
from typing import Optional

class StorageType(Enum):
    MINIO = "minio"
    S3 = "s3"
    LOCAL = "local"  # 开发/测试用

class StorageFactory:
    """存储服务工厂"""
    
    _instances: dict[str, StorageService] = {}
    
    @classmethod
    def get_storage(
        cls,
        storage_type: StorageType = StorageType.MINIO
    ) -> StorageService:
        key = storage_type.value
        
        if key not in cls._instances:
            cls._instances[key] = cls._create_storage(storage_type)
        
        return cls._instances[key]
    
    @classmethod
    def _create_storage(cls, storage_type: StorageType) -> StorageService:
        from unifiles.core.config.settings import settings
        
        if storage_type == StorageType.MINIO:
            return MinIOStorageService(
                endpoint=settings.minio.endpoint,
                access_key=settings.minio.access_key,
                secret_key=settings.minio.secret_key,
                secure=settings.minio.secure,
                region=settings.minio.region
            )
        elif storage_type == StorageType.S3:
            return S3StorageService(
                region=settings.aws.region,
                access_key=settings.aws.access_key,
                secret_key=settings.aws.secret_key
            )
        elif storage_type == StorageType.LOCAL:
            return LocalStorageService(
                base_path=settings.storage.local_path
            )
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
```

## 文件上传流程

### 直接上传

```python
async def upload_file(
    file: UploadFile,
    user_id: str,
    metadata: dict = None
) -> File:
    storage = StorageFactory.get_storage()
    
    # 生成文件 ID
    file_id = str(uuid.uuid4())
    
    # 构建存储键
    storage_key = f"raw/{user_id}/{file_id}/{file.filename}"
    
    # 计算文件哈希
    hasher = hashlib.sha256()
    content = await file.read()
    hasher.update(content)
    content_hash = hasher.hexdigest()
    
    # 上传到存储
    await storage.upload(
        bucket="unifiles-raw",
        key=storage_key,
        data=BytesIO(content),
        content_type=file.content_type,
        metadata={
            "user_id": user_id,
            "original_filename": file.filename,
            "content_hash": content_hash
        }
    )
    
    # 保存到数据库
    file_record = await save_file_record(
        file_id=file_id,
        user_id=user_id,
        filename=file.filename,
        storage_key=storage_key,
        content_hash=content_hash,
        file_size=len(content),
        mime_type=file.content_type,
        metadata=metadata
    )
    
    return file_record
```

### 预签名上传 (大文件)

```python
async def get_upload_url(
    user_id: str,
    filename: str,
    content_type: str
) -> dict:
    storage = StorageFactory.get_storage()
    
    # 生成文件 ID
    file_id = str(uuid.uuid4())
    storage_key = f"raw/{user_id}/{file_id}/{filename}"
    
    # 生成预签名上传 URL
    upload_url = await storage.get_presigned_url(
        bucket="unifiles-raw",
        key=storage_key,
        expires=3600,
        method="PUT"
    )
    
    # 预先创建文件记录 (状态为 pending)
    await create_pending_file_record(
        file_id=file_id,
        user_id=user_id,
        filename=filename,
        storage_key=storage_key
    )
    
    return {
        "file_id": file_id,
        "upload_url": upload_url,
        "expires_in": 3600
    }
```

## 文件下载流程

### 直接下载

```python
async def download_file(file_id: str, user_id: str) -> StreamingResponse:
    # 获取文件记录
    file_record = await get_file_record(file_id, user_id)
    if not file_record:
        raise FileNotFoundError(f"File {file_id} not found")
    
    storage = StorageFactory.get_storage()
    
    # 获取文件内容
    content = await storage.download(
        bucket="unifiles-raw",
        key=file_record.storage_key
    )
    
    return StreamingResponse(
        BytesIO(content),
        media_type=file_record.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.filename}"'
        }
    )
```

### 预签名下载

```python
async def get_download_url(
    file_id: str,
    user_id: str,
    expires: int = 3600
) -> str:
    # 获取文件记录
    file_record = await get_file_record(file_id, user_id)
    if not file_record:
        raise FileNotFoundError(f"File {file_id} not found")
    
    storage = StorageFactory.get_storage()
    
    # 生成预签名下载 URL
    return await storage.get_presigned_url(
        bucket="unifiles-raw",
        key=file_record.storage_key,
        expires=expires,
        method="GET"
    )
```

## 生命周期管理

### 缓存清理

```python
# MinIO 生命周期规则 (JSON)
lifecycle_config = {
    "Rules": [
        {
            "ID": "cleanup-cache",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "cache/"
            },
            "Expiration": {
                "Days": 1
            }
        },
        {
            "ID": "cleanup-exports",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "exports/"
            },
            "Expiration": {
                "Days": 7
            }
        }
    ]
}
```

### 软删除实现

```python
async def soft_delete_file(file_id: str, user_id: str) -> bool:
    """软删除文件 (标记删除，不立即清理存储)"""
    
    # 更新数据库记录
    await update_file_status(
        file_id=file_id,
        user_id=user_id,
        status="deleted",
        deleted_at=datetime.utcnow()
    )
    
    return True

async def hard_delete_file(file_id: str) -> bool:
    """硬删除文件 (清理存储)"""
    
    file_record = await get_file_record_by_id(file_id)
    if not file_record:
        return False
    
    storage = StorageFactory.get_storage()
    
    # 删除原始文件
    await storage.delete(
        bucket="unifiles-raw",
        key=file_record.storage_key
    )
    
    # 删除处理后的文件
    processed_prefix = f"processed/{file_record.user_id}/{file_id}/"
    processed_objects = await storage.list_objects(
        bucket="unifiles-processed",
        prefix=processed_prefix
    )
    
    for obj in processed_objects:
        await storage.delete(
            bucket="unifiles-processed",
            key=obj.key
        )
    
    # 删除数据库记录
    await delete_file_record(file_id)
    
    return True
```

### 定时清理任务

```python
async def cleanup_deleted_files():
    """清理已软删除超过 30 天的文件"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    # 查询待清理文件
    files_to_delete = await get_files_deleted_before(cutoff_date)
    
    for file_record in files_to_delete:
        try:
            await hard_delete_file(file_record.id)
            logger.info(f"Cleaned up file: {file_record.id}")
        except Exception as e:
            logger.error(f"Failed to cleanup file {file_record.id}: {e}")
```

## 高可用配置

### 分布式 MinIO

```yaml
# docker-compose-distributed.yml
services:
  minio1:
    image: minio/minio:latest
    command: server http://minio{1...4}/data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio1_data:/data
    hostname: minio1
    
  minio2:
    image: minio/minio:latest
    command: server http://minio{1...4}/data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio2_data:/data
    hostname: minio2
    
  minio3:
    image: minio/minio:latest
    command: server http://minio{1...4}/data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio3_data:/data
    hostname: minio3
    
  minio4:
    image: minio/minio:latest
    command: server http://minio{1...4}/data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio4_data:/data
    hostname: minio4
    
  nginx:
    image: nginx:latest
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "9000:9000"
    depends_on:
      - minio1
      - minio2
      - minio3
      - minio4
```

### 负载均衡配置

```nginx
# nginx.conf
upstream minio_servers {
    server minio1:9000;
    server minio2:9000;
    server minio3:9000;
    server minio4:9000;
}

server {
    listen 9000;
    server_name localhost;
    
    # 允许大文件上传
    client_max_body_size 1G;
    
    location / {
        proxy_pass http://minio_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 监控与告警

### 存储指标

```python
# 存储使用统计
async def get_storage_stats(user_id: str) -> dict:
    storage = StorageFactory.get_storage()
    
    # 统计原始文件
    raw_objects = await storage.list_objects(
        bucket="unifiles-raw",
        prefix=f"raw/{user_id}/"
    )
    raw_size = sum(obj.size for obj in raw_objects)
    raw_count = len(raw_objects)
    
    # 统计处理后文件
    processed_objects = await storage.list_objects(
        bucket="unifiles-processed",
        prefix=f"processed/{user_id}/"
    )
    processed_size = sum(obj.size for obj in processed_objects)
    
    return {
        "user_id": user_id,
        "raw_files": {
            "count": raw_count,
            "size_bytes": raw_size
        },
        "processed_files": {
            "size_bytes": processed_size
        },
        "total_size_bytes": raw_size + processed_size
    }
```

### 健康检查

```python
async def check_storage_health() -> dict:
    storage = StorageFactory.get_storage()
    
    results = {}
    buckets = ["unifiles-raw", "unifiles-processed", "unifiles-cache"]
    
    for bucket in buckets:
        try:
            # 尝试列出对象
            await storage.list_objects(bucket, prefix="", max_keys=1)
            results[bucket] = {"status": "healthy"}
        except Exception as e:
            results[bucket] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    return {
        "storage_type": "minio",
        "buckets": results,
        "overall": "healthy" if all(
            b["status"] == "healthy" for b in results.values()
        ) else "unhealthy"
    }
```

## 下一步

- [安全模型](./security-model.md) - 认证与授权设计
- [开发技巧](./development-tips.md) - 本地开发指南
