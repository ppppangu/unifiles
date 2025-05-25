# PDF 处理服务内存优化总结

## 🚨 原始问题

你发现的内存问题非常准确！原始代码存在严重的内存泄漏和过度使用问题：

### 1. **PDF 文件完全加载到内存**
- 整个 PDF 文件一次性读取到内存
- 大文件（如 100MB+ PDF）直接导致内存爆炸
- 没有文件大小限制

### 2. **图像处理内存泄漏**
- 每页高分辨率图像（150 DPI）同时生成
- 所有图像数据保存在内存中
- 没有及时释放图像资源

### 3. **无限制并发处理**
- 所有 OCR 任务同时启动
- 所有嵌入向量同时生成
- 内存峰值极高

## ✅ 优化方案

### 1. **文件大小限制**
```python
# 下载时检查大小
async def _download_pdf(url: str, max_size_mb: int = 100) -> bytes:
    # 流式下载，检查大小
    
# 上传时检查大小
size_mb = len(pdf_bytes) / (1024 * 1024)
if size_mb > 100:
    raise HTTPException(status_code=413, detail="文件过大")
```

### 2. **图像处理优化**
```python
# 降低分辨率：150 -> 120 DPI
img = page.to_image(resolution=120).original

# 压缩质量：默认 -> 85%
img.save(buf, format="JPEG", quality=85)

# 立即释放内存
img.close()
del img_bytes
```

### 3. **并发控制**
```python
# OCR 并发限制
max_concurrent_ocr: int = 3
ocr_semaphore = asyncio.Semaphore(max_concurrent_ocr)

# 嵌入向量分批处理
batch_size: int = 10
max_concurrent: int = 5
```

### 4. **内存监控**
```python
# 添加内存监控工具
from src.memory_monitor import MemoryMonitor, log_memory_usage

# 在关键步骤监控内存
with MemoryMonitor(f"[{job_id}] 文本提取"):
    text_pages = await pdf_utils.extract_text_pages(pdf_bytes)
```

### 5. **主动内存管理**
```python
# 及时释放大对象
del pdf_bytes
del text_pages
gc.collect()
```

## 📊 性能改进

| 优化项目 | 优化前 | 优化后 | 改进 |
|---------|--------|--------|------|
| 图像分辨率 | 150 DPI | 120 DPI | -20% |
| 图像质量 | 100% | 85% | -15% |
| OCR 并发 | 无限制 | 3 个 | 控制峰值 |
| 嵌入批大小 | 全部 | 10 个 | 分批处理 |
| 文件大小限制 | 无 | 100MB | 防止爆炸 |

## 🔧 关键优化点

### 1. **延迟图像生成**
```python
# 原来：所有页面立即生成图像
# 现在：需要时才生成，用完立即释放
def _generate_image() -> bytes:
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[page_idx]
        # 生成图像...
```

### 2. **分批嵌入处理**
```python
# 原来：所有文本块同时处理
tasks = [_embedding_request(c, session) for c in chunks]

# 现在：分批处理
for i in range(0, len(chunks), batch_size):
    batch = chunks[i:i + batch_size]
    # 处理批次...
```

### 3. **内存监控集成**
```python
# 每个处理步骤都有内存监控
with MemoryMonitor(f"[{job_id}] 步骤名称"):
    # 处理逻辑...
    # 自动记录内存变化
```

## 🎯 预期效果

1. **内存使用稳定**：不再出现内存爆炸
2. **处理大文件**：可以安全处理 100MB 以内的 PDF
3. **并发控制**：避免系统资源耗尽
4. **监控可见**：实时了解内存使用情况
5. **自动回收**：主动释放不需要的内存

## 🚀 使用建议

1. **监控日志**：关注内存使用日志
2. **调整参数**：根据服务器配置调整并发数
3. **文件限制**：根据需要调整文件大小限制
4. **定期检查**：监控长期运行的内存趋势

## 📝 配置参数

```python
# PDF 处理配置
MAX_PDF_SIZE_MB = 100           # 最大 PDF 文件大小
MAX_CONCURRENT_OCR = 3          # 最大并发 OCR 数
IMAGE_RESOLUTION = 120          # 图像分辨率 DPI
IMAGE_QUALITY = 85              # JPEG 压缩质量

# 嵌入处理配置
EMBEDDING_BATCH_SIZE = 10       # 嵌入批大小
MAX_CONCURRENT_EMBEDDING = 5    # 最大并发嵌入数
```

这些优化应该能显著改善内存使用情况，避免内存占满的问题！
