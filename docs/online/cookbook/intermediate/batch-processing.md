# 批量处理

本教程讲解如何高效处理大量文件，包括并发控制、错误处理和进度追踪。

## 基础批量处理

### 顺序处理

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

def process_files_sequential(file_paths: list):
    """顺序处理文件"""
    results = []
    
    for i, path in enumerate(file_paths):
        print(f"处理 {i+1}/{len(file_paths)}: {path}")
        
        # 上传
        file = client.files.upload(path)
        
        # 提取
        extraction = client.extractions.create(file_id=file.id)
        extraction.wait()
        
        results.append({
            "path": path,
            "file_id": file.id,
            "status": extraction.status
        })
    
    return results

# 使用
results = process_files_sequential([
    "doc1.pdf", "doc2.pdf", "doc3.pdf"
])
```

### 并发处理

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

def process_single_file(path: str) -> dict:
    """处理单个文件"""
    try:
        file = client.files.upload(path)
        extraction = client.extractions.create(file_id=file.id)
        extraction.wait()
        
        return {
            "path": path,
            "file_id": file.id,
            "status": "success",
            "pages": extraction.total_pages
        }
    except Exception as e:
        return {
            "path": path,
            "status": "error",
            "error": str(e)
        }

def process_files_concurrent(file_paths: list, max_workers: int = 5):
    """并发处理文件"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_path = {
            executor.submit(process_single_file, path): path
            for path in file_paths
        }
        
        # 收集结果
        for future in as_completed(future_to_path):
            result = future.result()
            results.append(result)
            print(f"完成: {result['path']} - {result['status']}")
    
    return results

# 使用（5个并发）
results = process_files_concurrent(file_paths, max_workers=5)
```

## 带速率限制的批处理

```python
import time
from unifiles import UnifilesClient
from unifiles.exceptions import RateLimitError

client = UnifilesClient(api_key="<api-key>")

def process_with_rate_limit(file_paths: list, rate_per_minute: int = 50):
    """带速率限制的批处理"""
    interval = 60.0 / rate_per_minute
    results = []
    
    for i, path in enumerate(file_paths):
        start_time = time.time()
        
        # 带重试的处理
        for attempt in range(3):
            try:
                file = client.files.upload(path)
                extraction = client.extractions.create(file_id=file.id)
                extraction.wait()
                
                results.append({
                    "path": path,
                    "file_id": file.id,
                    "status": "success"
                })
                break
                
            except RateLimitError as e:
                wait_time = e.retry_after or 60
                print(f"速率限制，等待 {wait_time}s...")
                time.sleep(wait_time)
                
            except Exception as e:
                if attempt == 2:
                    results.append({
                        "path": path,
                        "status": "error",
                        "error": str(e)
                    })
        
        # 速率控制
        elapsed = time.time() - start_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        
        # 进度报告
        if (i + 1) % 10 == 0:
            print(f"进度: {i+1}/{len(file_paths)}")
    
    return results
```

## 使用 Webhook 的异步批处理

推荐用于大规模处理：

```python
from unifiles import UnifilesClient
import json

client = UnifilesClient(api_key="<api-key>")

def submit_batch_async(file_paths: list, kb_id: str = None):
    """异步批量提交（使用 Webhook 接收结果）"""
    
    tasks = []
    
    for path in file_paths:
        # 上传
        file = client.files.upload(
            path=path,
            metadata={"batch_id": batch_id}
        )
        
        # 创建提取任务（不等待）
        extraction = client.extractions.create(file_id=file.id)
        
        tasks.append({
            "path": path,
            "file_id": file.id,
            "extraction_id": extraction.id
        })
    
    print(f"已提交 {len(tasks)} 个任务")
    print("结果将通过 Webhook 通知")
    
    # 保存任务列表供追踪
    with open(f"batch_{batch_id}.json", "w") as f:
        json.dump(tasks, f)
    
    return tasks

# Webhook 处理器（单独服务）
"""
@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    event = request.json
    
    if event["type"] == "extraction.completed":
        file_id = event["data"]["file_id"]
        
        # 如果配置了知识库，自动添加
        if kb_id:
            client.knowledge_bases.documents.create(
                kb_id=kb_id,
                file_id=file_id
            )
    
    return {"ok": True}
"""
```

## 批量添加到知识库

```python
def batch_add_to_kb(kb_id: str, file_ids: list, concurrency: int = 3):
    """批量将文件添加到知识库"""
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def add_single(file_id: str):
        try:
            doc = client.knowledge_bases.documents.create(
                kb_id=kb_id,
                file_id=file_id
            )
            doc.wait(timeout=300)
            return {"file_id": file_id, "doc_id": doc.id, "status": "indexed"}
        except Exception as e:
            return {"file_id": file_id, "status": "error", "error": str(e)}
    
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(add_single, fid): fid for fid in file_ids}
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"索引: {result['file_id']} - {result['status']}")
    
    return results

# 使用
file_ids = ["file_1", "file_2", "file_3"]
results = batch_add_to_kb("kb_xxx", file_ids)
```

## 完整批处理工作流

```python
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from unifiles import UnifilesClient
from unifiles.exceptions import UnifilesError

@dataclass
class BatchResult:
    total: int
    success: int
    failed: int
    results: List[dict]

class BatchProcessor:
    """批量文档处理器"""
    
    def __init__(self, api_key: str, kb_id: Optional[str] = None):
        self.client = UnifilesClient(api_key=api_key)
        self.kb_id = kb_id
    
    def process_directory(
        self,
        directory: str,
        pattern: str = "*.pdf",
        concurrency: int = 5
    ) -> BatchResult:
        """处理目录中的所有匹配文件"""
        
        # 收集文件
        path = Path(directory)
        files = list(path.glob(pattern))
        print(f"找到 {len(files)} 个文件")
        
        # 并发处理
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(self._process_file, str(f)): f
                for f in files
            }
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                
                status = "✓" if result["status"] == "success" else "✗"
                print(f"[{i+1}/{len(files)}] {status} {result['path']}")
        
        # 统计结果
        success = sum(1 for r in results if r["status"] == "success")
        
        return BatchResult(
            total=len(files),
            success=success,
            failed=len(files) - success,
            results=results
        )
    
    def _process_file(self, path: str) -> dict:
        """处理单个文件"""
        result = {"path": path}
        
        try:
            # 上传
            file = self.client.files.upload(path)
            result["file_id"] = file.id
            
            # 提取
            extraction = self.client.extractions.create(file_id=file.id)
            extraction.wait(timeout=300)
            
            if extraction.status != "completed":
                raise Exception(f"提取失败: {extraction.error}")
            
            result["pages"] = extraction.total_pages
            
            # 如果配置了知识库，添加文档
            if self.kb_id:
                doc = self.client.knowledge_bases.documents.create(
                    kb_id=self.kb_id,
                    file_id=file.id
                )
                doc.wait(timeout=300)
                result["doc_id"] = doc.id
                result["chunks"] = doc.chunk_count
            
            result["status"] = "success"
            
        except UnifilesError as e:
            result["status"] = "error"
            result["error"] = e.message
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result

# 使用
processor = BatchProcessor(
    api_key="<api-key>",
    kb_id="kb_xxx"  # 可选
)

result = processor.process_directory(
    directory="./documents",
    pattern="**/*.pdf",  # 递归匹配
    concurrency=5
)

print(f"\n处理完成:")
print(f"  成功: {result.success}")
print(f"  失败: {result.failed}")

# 查看失败的文件
failed = [r for r in result.results if r["status"] == "error"]
if failed:
    print("\n失败列表:")
    for r in failed:
        print(f"  {r['path']}: {r['error']}")
```

## 进度追踪与恢复

```python
import json
from pathlib import Path

class ResumableBatchProcessor:
    """支持断点续传的批处理器"""
    
    def __init__(self, api_key: str, checkpoint_file: str = "batch_checkpoint.json"):
        self.client = UnifilesClient(api_key=api_key)
        self.checkpoint_file = checkpoint_file
        self.processed = self._load_checkpoint()
    
    def _load_checkpoint(self) -> set:
        """加载已处理的文件列表"""
        if Path(self.checkpoint_file).exists():
            with open(self.checkpoint_file) as f:
                return set(json.load(f))
        return set()
    
    def _save_checkpoint(self, path: str):
        """保存检查点"""
        self.processed.add(path)
        with open(self.checkpoint_file, "w") as f:
            json.dump(list(self.processed), f)
    
    def process_files(self, file_paths: list):
        """处理文件，跳过已处理的"""
        
        # 过滤已处理的文件
        pending = [p for p in file_paths if p not in self.processed]
        print(f"待处理: {len(pending)}, 已跳过: {len(file_paths) - len(pending)}")
        
        results = []
        for i, path in enumerate(pending):
            try:
                # 处理文件
                file = self.client.files.upload(path)
                extraction = self.client.extractions.create(file_id=file.id)
                extraction.wait()
                
                # 保存检查点
                self._save_checkpoint(path)
                
                results.append({"path": path, "status": "success"})
                print(f"[{i+1}/{len(pending)}] ✓ {path}")
                
            except Exception as e:
                results.append({"path": path, "status": "error", "error": str(e)})
                print(f"[{i+1}/{len(pending)}] ✗ {path}: {e}")
        
        return results
    
    def reset_checkpoint(self):
        """重置检查点"""
        self.processed = set()
        Path(self.checkpoint_file).unlink(missing_ok=True)

# 使用
processor = ResumableBatchProcessor(api_key="<api-key>")

# 第一次运行（假设中途失败）
results = processor.process_files(file_paths)

# 重新运行（会跳过已处理的文件）
results = processor.process_files(file_paths)

# 完全重新处理
processor.reset_checkpoint()
results = processor.process_files(file_paths)
```

## 最佳实践

### 1. 合理设置并发数

```python
# 根据套餐调整
CONCURRENCY_BY_PLAN = {
    "free": 2,
    "professional": 5,
    "enterprise": 10
}
```

### 2. 实现错误重试

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=60)
)
def upload_with_retry(client, path):
    return client.files.upload(path)
```

### 3. 记录详细日志

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("batch_processor")

def process_file(path):
    logger.info(f"开始处理: {path}")
    try:
        # 处理逻辑
        logger.info(f"处理成功: {path}")
    except Exception as e:
        logger.error(f"处理失败: {path}, 错误: {e}")
```

## 下一步

- [Webhook 集成](webhook-integration.md) - 异步批处理通知
- [性能调优](../advanced/performance-tuning.md) - 优化大规模处理
- [多租户配置](../advanced/multi-tenant-setup.md) - 租户隔离批处理
