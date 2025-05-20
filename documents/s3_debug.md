# S3连接错误排查设计文档

## 问题描述
- 初始错误信息：'S3' object is not callable
- 修复后新错误：object dict can't be used in 'await' expression
- 现象：S3连接初始化时报错，无法正常使用S3相关功能。

## 排查与修复步骤 Checklist

- [x] 1. 定位所有S3 client的调用代码，检查是否有将S3 client对象当作函数调用的情况。
- [x] 2. 检查`async_get_s3_connection`的返回值使用方式，确保调用的是S3 client的方法而不是对象本身。
- [x] 3. 修正错误调用方式，改为`s3_client.method()`。
- [x] 4. 发现并修复`async_get_s3_connection`函数实现中的`asyncio.to_thread`使用问题。
- [x] 5. 发现并解决同步API与异步调用的兼容性问题，创建异步包装器。
- [ ] 6. 本地测试修复后的代码，确保S3连接和操作正常。
- [ ] 7. 总结经验，完善文档。

## 修复建议
- S3 client对象不能直接调用，需调用其方法。
- 推荐在代码中增加类型注解和注释，避免误用。
- `asyncio.to_thread`需要传递函数对象而非函数调用结果。
- 对于同步API，需要创建异步包装器以在异步环境中使用。

## 问题根因分析
1. 第一个问题出在`src/tools.py`中的`async_get_s3_connection`函数实现。函数中错误地将`boto3.client(...)`的结果（即S3 client对象）作为参数传递给了`asyncio.to_thread`。

2. 第二个问题是boto3是同步API，它的方法（如`list_buckets()`）返回的是直接结果，不是协程，无法直接await。因此需要创建一个包装器类，将同步API包装成异步API。

## 解决方案演进
1. 初始错误代码：
```python
await asyncio.to_thread(boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
))
```

2. 第一次修复（解决'S3' object is not callable问题）：
```python
await asyncio.to_thread(
    boto3.client,
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)
```

3. 最终修复（解决object dict can't be used in 'await' expression问题）：
创建了`AsyncS3Client`包装类，将boto3的同步API包装成异步API：
```python
class AsyncS3Client:
    def __init__(self, s3_client):
        self._client = s3_client
    
    async def list_buckets(self):
        return await asyncio.to_thread(self._client.list_buckets)
    
    # ...其他方法
```

## 进度跟踪
- 当前进度：已修复同步API与异步调用的兼容性问题，创建了异步包装器，准备测试验证。 