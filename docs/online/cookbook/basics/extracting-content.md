# 内容提取

本教程将带你从各种文档格式中提取结构化的 Markdown 内容。

## 前置条件

- 已完成 [第一次上传](your-first-upload.md)
- 有一个已上传的文件

## 步骤 1：创建提取任务

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 假设已有上传的文件
file = client.files.upload("report.pdf")

# 创建提取任务
extraction = client.extractions.create(file_id=file.id)

print(f"提取任务已创建: {extraction.id}")
print(f"状态: {extraction.status}")  # pending
```

## 步骤 2：等待提取完成

### 方式一：同步等待

```python
# 等待完成（最简单的方式）
extraction = extraction.wait(timeout=300)  # 最多等5分钟

if extraction.status == "completed":
    print("提取成功！")
    print(f"页数: {extraction.total_pages}")
else:
    print(f"提取失败: {extraction.error}")
```

### 方式二：轮询状态

```python
import time

while True:
    extraction = client.extractions.get(extraction.id)
    
    print(f"状态: {extraction.status}")
    
    if extraction.status == "completed":
        print("提取完成！")
        break
    elif extraction.status == "failed":
        print(f"提取失败: {extraction.error}")
        break
    
    time.sleep(2)  # 每2秒检查一次
```

### 方式三：使用 Webhook（推荐用于生产）

```python
# 配置 Webhook 接收完成通知
webhook = client.webhooks.create(
    url="https://your-app.com/webhook",
    events=["extraction.completed", "extraction.failed"]
)

# 创建提取任务后无需等待
extraction = client.extractions.create(file_id=file.id)
# Webhook 会在完成时通知你
```

## 步骤 3：获取提取结果

```python
extraction = client.extractions.get(extraction.id)

# 基本信息
print(f"任务ID: {extraction.id}")
print(f"文件ID: {extraction.file_id}")
print(f"状态: {extraction.status}")
print(f"模式: {extraction.mode}")

# 提取结果
print(f"总页数: {extraction.total_pages}")
print(f"Markdown长度: {len(extraction.markdown)} 字符")

# 查看内容预览
print("\n--- 内容预览 ---")
print(extraction.markdown[:1000])
print("...")
```

**输出示例：**

```
任务ID: ext_xyz789
文件ID: file_abc123
状态: completed
模式: normal
总页数: 15
Markdown长度: 25600 字符

--- 内容预览 ---
# 年度报告 2024

## 执行摘要

本年度公司实现了显著增长，主要亮点包括...

## 第一章 业务回顾

### 1.1 市场表现

| 指标 | 2023 | 2024 | 增长率 |
|-----|------|------|-------|
| 营收 | 1000万 | 1500万 | +50% |
| 利润 | 200万 | 350万 | +75% |
...
```

## 选择提取模式

Unifiles 提供三种提取模式：

### simple 模式 - 快速提取

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="simple"
)
```

- ✅ 处理速度最快
- ✅ 适合纯文本文档
- ❌ 不进行 OCR
- ❌ 不保留复杂排版

**适用场景：** `.txt`、`.md`、简单的 `.html`

### normal 模式 - 标准提取（默认）

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="normal"
)
```

- ✅ 平衡速度和质量
- ✅ 智能判断是否需要 OCR
- ✅ 保留基本结构
- ❌ 可能遗漏复杂排版

**适用场景：** 大多数 PDF、Word 文档

### advanced 模式 - 高精度提取

```python
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "preserve_layout": True,
        "extract_tables": True
    }
)
```

- ✅ 最高提取质量
- ✅ 高精度 OCR
- ✅ 完整保留排版
- ❌ 处理时间较长

**适用场景：** 扫描件、复杂排版文档、学术论文

### 模式对比

```python
# 测试不同模式
modes = ["simple", "normal", "advanced"]

for mode in modes:
    extraction = client.extractions.create(
        file_id=file.id,
        mode=mode
    )
    extraction.wait()
    
    print(f"\n{mode} 模式:")
    print(f"  处理时间: {extraction.processing_time}s")
    print(f"  内容长度: {len(extraction.markdown)} 字符")
```

## 提取选项

### 指定语言

```python
# 提高中文 OCR 准确率
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={"language": "zh"}
)
```

支持的语言：`zh`（中文）、`en`（英文）、`ja`（日文）、`ko`（韩文）

### 表格提取

```python
extraction = client.extractions.create(
    file_id=file.id,
    options={
        "extract_tables": True,
        "table_format": "markdown"  # markdown | html | json
    }
)
```

## 完整示例

```python
from unifiles import UnifilesClient
from unifiles.exceptions import ProcessingError

def extract_document(file_path: str) -> str:
    """上传文件并提取内容"""
    
    client = UnifilesClient(api_key="sk_...")
    
    # 1. 上传文件
    print(f"正在上传: {file_path}")
    file = client.files.upload(file_path)
    print(f"✓ 上传成功: {file.id}")
    
    # 2. 判断合适的模式
    if file.content_type in ["text/plain", "text/markdown"]:
        mode = "simple"
    elif file.content_type.startswith("image/"):
        mode = "advanced"  # 图片需要 OCR
    else:
        mode = "normal"
    
    print(f"使用 {mode} 模式提取...")
    
    # 3. 创建提取任务
    try:
        extraction = client.extractions.create(
            file_id=file.id,
            mode=mode,
            options={"language": "zh"}
        )
        
        # 4. 等待完成
        extraction = extraction.wait(timeout=300)
        
        if extraction.status == "completed":
            print(f"✓ 提取成功")
            print(f"  页数: {extraction.total_pages}")
            print(f"  内容长度: {len(extraction.markdown)} 字符")
            return extraction.markdown
        else:
            print(f"✗ 提取失败: {extraction.error}")
            return None
            
    except ProcessingError as e:
        print(f"✗ 处理错误: {e.message}")
        return None

# 使用
content = extract_document("annual_report.pdf")
if content:
    # 保存为 Markdown 文件
    with open("extracted.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("已保存到 extracted.md")
```

## 处理不同文档类型

### PDF 文档

```python
# 普通 PDF
extraction = client.extractions.create(
    file_id=pdf_file.id,
    mode="normal"
)

# 扫描件 PDF
extraction = client.extractions.create(
    file_id=scanned_pdf.id,
    mode="advanced",
    options={"language": "zh"}
)
```

### Word 文档

```python
# Word 文档通常 normal 模式即可
extraction = client.extractions.create(
    file_id=docx_file.id,
    mode="normal"
)
```

### 图片

```python
# 图片必须使用 advanced 模式进行 OCR
extraction = client.extractions.create(
    file_id=image_file.id,
    mode="advanced",
    options={
        "language": "zh",
        "ocr_provider": "default"
    }
)
```

### Excel 表格

```python
extraction = client.extractions.create(
    file_id=excel_file.id,
    mode="normal",
    options={"extract_tables": True}
)

# Excel 会被转换为 Markdown 表格
```

## 错误处理

```python
from unifiles.exceptions import ProcessingError, ValidationError

try:
    extraction = client.extractions.create(file_id=file.id)
    extraction.wait()
    
except ValidationError as e:
    if e.code == "UNSUPPORTED_FORMAT":
        print("不支持的文件格式")
    elif e.code == "FILE_NOT_FOUND":
        print("文件不存在")
        
except ProcessingError as e:
    if e.code == "OCR_FAILED":
        print("OCR 识别失败，尝试降级...")
        # 尝试使用 simple 模式
        extraction = client.extractions.create(
            file_id=file.id,
            mode="simple"
        )
    elif e.code == "EXTRACTION_TIMEOUT":
        print("提取超时，请稍后重试")
    elif e.code == "ENCRYPTED_FILE":
        print("文件有密码保护，请移除密码后重试")
```

## 最佳实践

### 1. 根据文件类型选择模式

```python
def choose_mode(file):
    """智能选择提取模式"""
    content_type = file.content_type
    
    if content_type in ["text/plain", "text/markdown"]:
        return "simple"
    elif content_type.startswith("image/"):
        return "advanced"
    elif content_type == "application/pdf":
        # PDF 可能是扫描件
        return "normal"  # 或根据需要选择 advanced
    else:
        return "normal"
```

### 2. 处理大文件时使用 Webhook

```python
# 大文件可能需要较长时间
if file.size > 10 * 1024 * 1024:  # > 10MB
    # 使用 Webhook 而不是同步等待
    extraction = client.extractions.create(file_id=file.id)
    print(f"提取任务已创建: {extraction.id}")
    print("完成后将通过 Webhook 通知")
```

### 3. 保存提取结果

```python
# 提取结果可以重复使用
extraction = client.extractions.get(extraction_id)

# 不需要重新提取
markdown = extraction.markdown
```

## 下一步

提取完成后，你可以：

- [构建知识库](building-knowledge-base.md) - 将提取内容索引到知识库
- [理解 Markdown 输出](../foundational/understanding-output.md) - 深入了解输出格式
- [分块策略详解](../intermediate/chunking-strategies.md) - 为 RAG 优化分块
