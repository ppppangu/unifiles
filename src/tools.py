import asyncio
import boto3
from typing import Any, Dict, List

# 创建S3客户端的包装器，添加异步方法
class AsyncS3Client:
    def __init__(self, s3_client):
        self._client = s3_client
    
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """异步包装同步的list_buckets方法"""
        return await asyncio.to_thread(self._client.list_buckets)
    
    async def close(self):
        """关闭S3连接（如果需要）"""
        if hasattr(self._client, 'close'):
            return await asyncio.to_thread(self._client.close)

    # 可以根据需要添加更多方法
    def __getattr__(self, name):
        """对于未定义的方法，返回原始客户端的方法"""
        return getattr(self._client, name)

# 异步封装获得s3连接
async def async_get_s3_connection(endpoint_url, aws_access_key_id, aws_secret_access_key, region_name) -> AsyncS3Client:
    s3_client = await asyncio.to_thread(
        boto3.client,
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name
    )
    return AsyncS3Client(s3_client)

