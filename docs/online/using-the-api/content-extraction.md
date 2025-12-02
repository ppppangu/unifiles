# 内容提取

内容提取是 Unifiles 三层架构的第二层，负责将上传的文件转换为结构化的 Markdown 内容。这是连接原始文件和知识库的关键桥梁。

## 提取流程概述

```
文件上传 → 格式检测 → 内容解析 → OCR识别(可选) → Markdown转换 → 存储
```

每个提取任务都会：

1. 检测文件类型和编码
2. 使用对应的解析器处理内容
3. 如果是扫描件，自动进行 OCR 识别
4. 将所有内容统一转换为 Markdown 格式
5. 提取元数据（页数、标题、作者等）

## SDK 使用

### 创建提取任务

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 先上传文件
file = client.files.upload("document.pdf")

# 创建提取任务
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal",  # simple | normal | advanced
    options={
        "language": "zh",
        "ocr_provider": "default"
    }
)

print(f"提取任务已创建: {extraction.id}")
print(f"状态: {extraction.status}")  # pending -> processing -> completed
```

### 等待提取完成

有两种方式获取提取结果：

**方式一：同步等待**

```python
# 等待任务完成（默认超时 300 秒）
extraction = extraction.wait(timeout=300)

if extraction.status == "completed":
    print(f"提取成功！")
    print(f"Markdown内容长度: {len(extraction.markdown)} 字符")
    print(f"总页数: {extraction.total_pages}")
else:
    print(f"提取失败: {extraction.error}")
```

**方式二：轮询状态**

```python
import time

while True:
    extraction = client.extractions.get(extraction.id)
    
    if extraction.status == "completed":
        print("提取完成！")
        break
    elif extraction.status == "failed":
        print(f"提取失败: {extraction.error}")
        break
    else:
        print(f"当前状态: {extraction.status}")
        time.sleep(2)
```

### 获取提取结果

```python
# 获取提取任务详情
extraction = client.extractions.get(extraction_id)

# 访问结果
print(extraction.id)           # 提取任务ID
print(extraction.file_id)      # 关联的文件ID
print(extraction.status)       # pending | processing | completed | failed
print(extraction.mode)         # simple | normal | advanced
print(extraction.markdown)     # 提取的Markdown内容
print(extraction.total_pages)  # 文档总页数
print(extraction.created_at)   # 创建时间
print(extraction.completed_at) # 完成时间
print(extraction.error)        # 错误信息（如果失败）
```

### 获取文件的提取历史

```python
# 获取某个文件的所有提取记录
extractions = client.extractions.list(file_id=file.id)

for ext in extractions.items:
    print(f"{ext.id}: {ext.status} ({ext.mode})")
```

## REST API

### 创建提取任务

```http
POST /v1/extractions
Authorization: Bearer sk_...
Content-Type: application/json

{
    "file_id": "file_abc123",
    "mode": "normal",
    "options": {
        "language": "zh",
        "ocr_provider": "default"
    }
}
```

**响应：**

```json
{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "pending",
    "mode": "normal",
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 获取提取状态

```http
GET /v1/extractions/{extraction_id}
Authorization: Bearer sk_...
```

**响应（处理中）：**

```json
{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "processing",
    "mode": "normal",
    "progress": 45,
    "created_at": "2024-01-15T10:30:00Z"
}
```

**响应（完成）：**

```json
{
    "id": "ext_xyz789",
    "file_id": "file_abc123",
    "status": "completed",
    "mode": "normal",
    "markdown": "# 文档标题\n\n这是提取的内容...",
    "total_pages": 15,
    "metadata": {
        "title": "文档标题",
        "author": "作者名",
        "created_date": "2024-01-01"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:31:30Z"
}
```

### 获取文件的提取记录

```http
GET /v1/files/{file_id}/extractions
Authorization: Bearer sk_...
```

**响应：**

```json
{
    "items": [
        {
            "id": "ext_xyz789",
            "status": "completed",
            "mode": "normal",
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "total": 1
}
```

## 提取模式

Unifiles 提供三种提取模式，适应不同的场景：

### simple 模式

最快速的提取模式，适合纯文本文档。

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="simple"
)
```

**特点：**

- 处理速度最快
- 不进行 OCR 识别
- 不解析复杂排版
- 适合：纯文本、Markdown、简单HTML

### normal 模式（默认）

平衡速度和质量的标准模式。

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal"
)
```

**特点：**

- 智能判断是否需要 OCR
- 保留基本排版结构
- 提取表格和列表
- 适合：大多数 PDF、Word 文档

### advanced 模式

最高质量的提取模式，适合复杂文档。

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "preserve_layout": True,
        "extract_tables": True,
        "extract_images": True
    }
)
```

**特点：**

- 使用高精度 OCR
- 保留完整排版结构
- 提取嵌入式图表
- 识别复杂表格
- 适合：扫描件、复杂排版文档、学术论文

## 提取选项

### 语言设置

指定文档的主要语言，提高 OCR 准确率：

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal",
    options={
        "language": "zh"  # zh(中文), en(英文), ja(日文), ko(韩文)
    }
)
```

### OCR 提供者

选择 OCR 引擎：

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "ocr_provider": "default"  # default | tesseract | cloud
    }
)
```

| 提供者 | 说明 | 适用场景 |
|-------|------|---------|
| `default` | 系统默认引擎 | 大多数场景 |
| `tesseract` | 开源 Tesseract | 自部署环境 |
| `cloud` | 云端高精度 OCR | 复杂扫描件 |

### 表格提取

控制表格处理方式：

```python
extraction = client.extractions.create(
    file_id=file.id,
    options={
        "extract_tables": True,
        "table_format": "markdown"  # markdown | html | json
    }
)
```

## 支持的文件格式

| 格式 | 扩展名 | simple | normal | advanced |
|-----|--------|--------|--------|----------|
| PDF | `.pdf` | ✓ | ✓ | ✓ |
| Word | `.docx`, `.doc` | ✓ | ✓ | ✓ |
| Excel | `.xlsx`, `.xls` | ✓ | ✓ | ✓ |
| PowerPoint | `.pptx`, `.ppt` | - | ✓ | ✓ |
| 纯文本 | `.txt`, `.md` | ✓ | ✓ | ✓ |
| HTML | `.html`, `.htm` | ✓ | ✓ | ✓ |
| 图片 | `.png`, `.jpg`, `.jpeg` | - | ✓ | ✓ |

## Markdown 输出格式

所有提取结果都以 Markdown 格式返回，遵循统一的结构：

```markdown
# 文档标题

## 第一章

这是正文内容...

### 1.1 小节

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |

## 第二章

更多内容...

---
提取元数据:
- 原文件: document.pdf
- 页数: 15
- 提取时间: 2024-01-15T10:31:30Z
```

### 为什么选择 Markdown？

1. **通用性**：几乎所有 LLM 都能很好地理解 Markdown
2. **可读性**：人类和机器都易于阅读
3. **轻量级**：比 HTML/JSON 更紧凑
4. **结构化**：保留标题层级、列表、表格等结构
5. **可转换**：轻松转换为其他格式（HTML、PDF 等）

## 错误处理

### 常见错误

```python
try:
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
except UnifilesError as e:
    if e.code == "FILE_NOT_FOUND":
        print("文件不存在")
    elif e.code == "UNSUPPORTED_FORMAT":
        print("不支持的文件格式")
    elif e.code == "EXTRACTION_TIMEOUT":
        print("提取超时，请稍后重试")
    elif e.code == "OCR_FAILED":
        print("OCR识别失败")
```

### 处理失败的提取

```python
extraction = client.extractions.get(extraction_id)

if extraction.status == "failed":
    print(f"错误代码: {extraction.error.code}")
    print(f"错误信息: {extraction.error.message}")
    
    # 尝试使用不同模式重新提取
    if extraction.error.code == "OCR_FAILED":
        new_extraction = client.extractions.create(
            file_id=extraction.file_id,
            mode="simple"  # 降级到simple模式
        )
```

## 最佳实践

### 1. 选择合适的提取模式

```python
def choose_extraction_mode(file):
    """根据文件类型选择提取模式"""
    if file.content_type in ["text/plain", "text/markdown"]:
        return "simple"
    elif file.content_type == "application/pdf":
        # PDF可能是扫描件，使用normal或advanced
        return "normal"
    elif file.content_type.startswith("image/"):
        # 图片必须使用OCR
        return "advanced"
    else:
        return "normal"
```

### 2. 批量提取时使用 Webhook

```python
# 创建Webhook接收完成通知
webhook = client.webhooks.create(
    url="https://your-app.com/webhook",
    events=["extraction.completed"]
)

# 批量创建提取任务（无需等待）
for file in files:
    client.extractions.create(file_id=file.id)
    # 完成后会通过Webhook通知
```

### 3. 监控提取进度

```python
def track_extraction_progress(extraction_id):
    """追踪提取进度"""
    while True:
        ext = client.extractions.get(extraction_id)
        
        if ext.status == "completed":
            return ext
        elif ext.status == "failed":
            raise Exception(f"提取失败: {ext.error}")
        
        # 显示进度
        progress = ext.progress or 0
        print(f"\r提取进度: {progress}%", end="")
        
        time.sleep(1)
```

### 4. 处理大文件

对于大文件，建议增加超时时间：

```python
# 大文件可能需要更长时间
extraction = client.extractions.create(
    file_id=large_file.id,
    mode="advanced"
)

# 设置较长的超时时间
extraction.wait(timeout=600)  # 10分钟
```

## 下一步

- [知识库](knowledge-bases.md) - 将提取的内容构建成可搜索的知识库
- [Webhook](webhooks.md) - 配置异步通知
- [错误处理](error-handling.md) - 详细的错误码和处理方式
