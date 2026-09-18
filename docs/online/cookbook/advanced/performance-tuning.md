# 性能调优

本教程讲解如何优化 Unifiles 在大规模部署场景下的性能，包括提取、索引和搜索的优化策略。

## 性能瓶颈分析

```
常见性能瓶颈：
├── 上传：网络带宽、并发连接数
├── 提取：CPU/GPU 资源、OCR 速度
├── 索引：向量计算、数据库写入
└── 搜索：向量检索、结果排序
```

## 上传优化

### 并发上传

```python
from concurrent.futures import ThreadPoolExecutor
from unifiles import UnifilesClient
import time

client = UnifilesClient(api_key="<api-key>")

def upload_with_metrics(path: str) -> dict:
    """上传并记录指标"""
    start = time.time()
    file = client.files.upload(path)
    elapsed = time.time() - start
    
    return {
        "file_id": file.id,
        "size": file.size,
        "time": elapsed,
        "speed_mbps": (file.size / 1024 / 1024) / elapsed
    }

def batch_upload_optimized(file_paths: list, max_workers: int = 10):
    """优化的批量上传"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(upload_with_metrics, p): p for p in file_paths}
        
        for future in futures:
            result = future.result()
            results.append(result)
    
    # 统计
    total_size = sum(r["size"] for r in results)
    total_time = max(r["time"] for r in results)  # 并发时间
    
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    print(f"总时间: {total_time:.2f}s")
    print(f"吞吐量: {(total_size / 1024 / 1024) / total_time:.2f} MB/s")
    
    return results
```

### 分片上传（大文件）

```python
def upload_large_file(file_path: str, chunk_size: int = 10 * 1024 * 1024):
    """分片上传大文件"""
    import os
    
    file_size = os.path.getsize(file_path)
    
    if file_size <= chunk_size:
        # 小文件直接上传
        return client.files.upload(file_path)
    
    # 大文件分片上传
    # 注：需要服务端支持分片上传 API
    upload_session = client.files.create_upload_session(
        filename=os.path.basename(file_path),
        total_size=file_size
    )
    
    with open(file_path, "rb") as f:
        chunk_index = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            client.files.upload_chunk(
                session_id=upload_session.id,
                chunk_index=chunk_index,
                data=chunk
            )
            chunk_index += 1
    
    return client.files.complete_upload(upload_session.id)
```

## 提取优化

### 选择合适的提取模式

```python
def optimized_extraction(file_id: str, file_info: dict):
    """根据文件特征选择最优提取模式"""
    
    content_type = file_info["content_type"]
    size = file_info["size"]
    
    # 纯文本：使用 simple 模式
    if content_type in ["text/plain", "text/markdown"]:
        mode = "simple"
    
    # 小型 PDF（< 1MB）：normal 模式
    elif content_type == "application/pdf" and size < 1024 * 1024:
        mode = "normal"
    
    # 大型 PDF 或图片：advanced 模式 + 并行处理
    elif content_type.startswith("image/") or size > 5 * 1024 * 1024:
        mode = "advanced"
    
    else:
        mode = "normal"
    
    return client.extractions.create(
        file_id=file_id,
        mode=mode,
        options={"parallel_pages": True}  # 启用页面并行处理
    )
```

### 批量提取优化

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def batch_extract_optimized(file_ids: list, concurrency: int = 5):
    """优化的批量提取"""
    
    # 阶段1：并发创建提取任务（不等待）
    extractions = []
    for file_id in file_ids:
        ext = client.extractions.create(file_id=file_id)
        extractions.append(ext)
    
    print(f"已创建 {len(extractions)} 个提取任务")
    
    # 阶段2：并发等待完成
    def wait_extraction(ext):
        try:
            ext.wait(timeout=300)
            return {"id": ext.id, "status": ext.status}
        except Exception as e:
            return {"id": ext.id, "status": "error", "error": str(e)}
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(wait_extraction, extractions))
    
    return results
```

## 索引优化

### 分块策略优化

```python
# 根据用途选择分块策略
CHUNKING_STRATEGIES = {
    # 高精度问答：小分块
    "qa": {
        "type": "semantic",
        "chunk_size": 256,
        "overlap": 30
    },
    # 综合检索：中等分块
    "general": {
        "type": "semantic",
        "chunk_size": 512,
        "overlap": 50
    },
    # 摘要生成：大分块
    "summary": {
        "type": "semantic",
        "chunk_size": 1024,
        "overlap": 100
    },
    # 快速索引：固定分块
    "fast": {
        "type": "fixed",
        "chunk_size": 512,
        "overlap": 50
    }
}

def create_optimized_kb(name: str, use_case: str = "general"):
    """创建优化的知识库"""
    strategy = CHUNKING_STRATEGIES.get(use_case, CHUNKING_STRATEGIES["general"])
    
    return client.knowledge_bases.create(
        name=name,
        chunking_strategy=strategy
    )
```

### 批量索引优化

```python
def batch_index_documents(kb_id: str, file_ids: list, batch_size: int = 10):
    """批量索引文档"""
    
    results = []
    
    for i in range(0, len(file_ids), batch_size):
        batch = file_ids[i:i+batch_size]
        
        # 并发添加文档
        docs = []
        for file_id in batch:
            doc = client.knowledge_bases.documents.create(
                kb_id=kb_id,
                file_id=file_id
            )
            docs.append(doc)
        
        # 等待批次完成
        for doc in docs:
            doc.wait(timeout=300)
            results.append({
                "doc_id": doc.id,
                "status": doc.status,
                "chunks": doc.chunk_count
            })
        
        print(f"已索引 {len(results)}/{len(file_ids)}")
    
    return results
```

## 搜索优化

### 搜索参数优化

```python
def optimized_search(kb_id: str, query: str, use_case: str = "qa"):
    """优化的搜索"""
    
    # 根据用例调整参数
    params = {
        "qa": {
            "top_k": 3,
            "threshold": 0.8,
            "mode": "semantic"
        },
        "research": {
            "top_k": 10,
            "threshold": 0.6,
            "mode": "hybrid"
        },
        "exploration": {
            "top_k": 20,
            "threshold": 0.4,
            "mode": "hybrid"
        }
    }
    
    p = params.get(use_case, params["qa"])
    
    if p["mode"] == "semantic":
        return client.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            top_k=p["top_k"],
            threshold=p["threshold"]
        )
    else:
        return client.knowledge_bases.hybrid_search(
            kb_id=kb_id,
            query=query,
            top_k=p["top_k"],
            vector_weight=0.7,
            keyword_weight=0.3
        )
```

### 搜索结果缓存

```python
import hashlib
import redis
import json

redis_client = redis.Redis()

def cached_search(kb_id: str, query: str, top_k: int = 5, cache_ttl: int = 300):
    """带缓存的搜索"""
    
    # 生成缓存键
    cache_key = hashlib.md5(
        f"{kb_id}:{query}:{top_k}".encode()
    ).hexdigest()
    cache_key = f"search:{cache_key}"
    
    # 检查缓存
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 执行搜索
    results = client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        top_k=top_k
    )
    
    # 缓存结果
    redis_client.setex(
        cache_key,
        cache_ttl,
        json.dumps(results.dict())
    )
    
    return results
```

### 预热常用查询

```python
def warm_up_search_cache(kb_id: str, common_queries: list):
    """预热搜索缓存"""
    
    for query in common_queries:
        cached_search(kb_id, query, cache_ttl=3600)
    
    print(f"已预热 {len(common_queries)} 个查询")
```

## 自部署性能配置

### Worker 配置

```python
# config/worker.py

WORKER_CONFIG = {
    # 提取 Worker
    "extraction": {
        "concurrency": 4,           # 并发数
        "max_memory_mb": 4096,      # 最大内存
        "timeout_seconds": 300,     # 超时时间
        "retry_count": 3            # 重试次数
    },
    
    # 索引 Worker
    "indexing": {
        "concurrency": 8,
        "batch_size": 100,          # 批量大小
        "embedding_batch": 32       # 嵌入批量
    }
}
```

### 数据库连接池

```python
# config/database.py

DATABASE_CONFIG = {
    "postgres": {
        "min_connections": 5,
        "max_connections": 20,
        "connection_timeout": 30,
        "command_timeout": 60
    },
    "redis": {
        "max_connections": 50,
        "socket_timeout": 5
    }
}
```

### 向量索引配置

```python
# pgvector 索引配置
VECTOR_INDEX_CONFIG = {
    # 小型知识库（< 10万向量）
    "small": {
        "index_type": "ivfflat",
        "lists": 100
    },
    # 中型知识库（10万-100万向量）
    "medium": {
        "index_type": "ivfflat",
        "lists": 1000
    },
    # 大型知识库（> 100万向量）
    "large": {
        "index_type": "hnsw",
        "m": 16,
        "ef_construction": 64
    }
}
```

## 监控与告警

### 性能指标收集

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# 定义指标
extraction_duration = Histogram(
    'unifiles_extraction_duration_seconds',
    'Time spent extracting documents',
    ['mode']
)

search_duration = Histogram(
    'unifiles_search_duration_seconds',
    'Time spent searching',
    ['kb_id']
)

active_extractions = Gauge(
    'unifiles_active_extractions',
    'Number of active extraction tasks'
)

# 使用示例
def monitored_extraction(file_id: str, mode: str = "normal"):
    active_extractions.inc()
    start = time.time()
    
    try:
        extraction = client.extractions.create(file_id=file_id, mode=mode)
        extraction.wait()
        return extraction
    finally:
        extraction_duration.labels(mode=mode).observe(time.time() - start)
        active_extractions.dec()
```

### 告警规则

```yaml
# prometheus/alerts.yml
groups:
  - name: unifiles
    rules:
      - alert: HighExtractionLatency
        expr: histogram_quantile(0.95, unifiles_extraction_duration_seconds) > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "提取延迟过高"
      
      - alert: HighSearchLatency
        expr: histogram_quantile(0.95, unifiles_search_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "搜索延迟过高"
```

## 性能基准测试

```python
import time
import statistics

def benchmark_extraction(file_paths: list, iterations: int = 3):
    """提取性能基准测试"""
    
    results = []
    
    for path in file_paths:
        times = []
        
        for _ in range(iterations):
            file = client.files.upload(path)
            
            start = time.time()
            extraction = client.extractions.create(file_id=file.id)
            extraction.wait()
            elapsed = time.time() - start
            
            times.append(elapsed)
            
            # 清理
            client.files.delete(file.id)
        
        results.append({
            "file": path,
            "avg_time": statistics.mean(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0
        })
    
    return results

def benchmark_search(kb_id: str, queries: list, iterations: int = 10):
    """搜索性能基准测试"""
    
    results = []
    
    for query in queries:
        times = []
        
        for _ in range(iterations):
            start = time.time()
            client.knowledge_bases.search(kb_id=kb_id, query=query, top_k=5)
            elapsed = time.time() - start
            times.append(elapsed)
        
        results.append({
            "query": query,
            "avg_ms": statistics.mean(times) * 1000,
            "p95_ms": sorted(times)[int(len(times) * 0.95)] * 1000
        })
    
    return results
```

## 下一步

- [RAG 效果评估](rag-evaluation.md) - 评估优化效果
- [自部署指南](../../self-hosting/index.md) - 详细部署配置
- [批量处理](../intermediate/batch-processing.md) - 批处理最佳实践
