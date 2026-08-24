# 文件和上传

本文介绍如何使用 Unifiles API 上传、管理和下载文件（Layer 1 操作）。

## 支持的文件格式

Unifiles 支持以下文件格式：

| 类别 | 格式 | MIME 类型 |
|------|------|-----------|
| **文档** | PDF | `application/pdf` |
| | Word (.doc, .docx) | `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| | Excel (.xls, .xlsx) | `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| | PowerPoint (.ppt, .pptx) | `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| **图片** | JPEG, PNG, TIFF, BMP | `image/jpeg`, `image/png`, `image/tiff`, `image/bmp` |
| **文本** | TXT, Markdown, CSV | `text/plain`, `text/markdown`, `text/csv` |

### 获取支持的格式列表

```python
types = client.files.types()
print(types.document_types)  # ['.pdf', '.doc', '.docx', ...]
print(types.image_types)     # ['.jpg', '.jpeg', '.png', ...]
print(types.all_types)       # 所有支持的格式
```

---

## 上传文件

### 基本上传

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...")

# 上传本地文件
file = client.files.upload("document.pdf")

print(f"文件 ID: {file.id}")
print(f"文件名: {file.filename}")
print(f"大小: {file.size} bytes")
print(f"类型: {file.mime_type}")
print(f"状态: {file.status}")  # uploaded
```

### 带元数据上传

```python
file = client.files.upload(
    path="contract.pdf",
    tags=["legal", "contract", "2024"],
    metadata={
        "project": "merger-acquisition",
        "department": "legal",
        "confidential": True
    }
)

print(f"标签: {file.tags}")
print(f"元数据: {file.metadata}")
```

### 上传字节数据

```python
# 从内存上传
with open("document.pdf", "rb") as f:
    content = f.read()

file = client.files.upload_bytes(
    content=content,
    filename="document.pdf",
    content_type="application/pdf"
)
```

### REST API 上传

```bash
curl -X POST "https://api.unifiles.dev/v1/files" \
  -H "Authorization: Bearer sk_..." \
  -F "file=@document.pdf" \
  -F 'tags=["legal", "2024"]' \
  -F 'metadata={"project": "demo"}'
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "f_abc123...",
    "filename": "document.pdf",
    "original_filename": "document.pdf",
    "mime_type": "application/pdf",
    "bytes": 1024768,
    "status": "uploaded",
    "file_hash": "sha256:...",
    "tags": ["legal", "2024"],
    "metadata": {"project": "demo"},
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

## 文件大小限制

| 环境 | 单文件限制 | 说明 |
|------|-----------|------|
| SaaS 免费版 | 10 MB | 可升级 |
| SaaS 专业版 | 100 MB | - |
| SaaS 企业版 | 500 MB | 可定制 |
| 自部署 | 可配置 | 默认 100 MB |

超过限制会返回错误：

```json
{
  "success": false,
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File size exceeds limit",
    "details": {
      "size": 157286400,
      "limit": 104857600
    }
  }
}
```

---

## 列出文件

### 基本列表

```python
files = client.files.list()

for f in files.items:
    print(f"{f.id}: {f.filename} ({f.bytes} bytes)")

print(f"总数: {files.total}")
print(f"是否有更多: {files.has_more}")
```

### 分页查询

```python
# 第一页
page1 = client.files.list(limit=20, offset=0)

# 第二页
page2 = client.files.list(limit=20, offset=20)

# 遍历所有文件
offset = 0
while True:
    result = client.files.list(limit=50, offset=offset)
    for f in result.items:
        process_file(f)
    
    if not result.has_more:
        break
    offset += 50
```

### 按条件过滤

```python
# 按标签过滤
legal_files = client.files.list(tags=["legal"])

# 按状态过滤
uploaded_files = client.files.list(status="uploaded")

# 组合过滤
files = client.files.list(
    tags=["contract"],
    status="uploaded",
    limit=10
)
```

### REST API 列表

```bash
curl -X GET "https://api.unifiles.dev/v1/files?limit=20&offset=0&tags=legal" \
  -H "Authorization: Bearer sk_..."
```

---

## 获取文件信息

### 获取单个文件

```python
file = client.files.get(file_id="f_abc123")

print(f"ID: {file.id}")
print(f"文件名: {file.filename}")
print(f"原始文件名: {file.original_filename}")
print(f"MIME 类型: {file.mime_type}")
print(f"大小: {file.size}")
print(f"哈希: {file.file_hash}")
print(f"状态: {file.status}")
print(f"标签: {file.tags}")
print(f"元数据: {file.metadata}")
print(f"创建时间: {file.created_at}")
```

### 文件状态

| 状态 | 说明 |
|------|------|
| `uploaded` | 已上传，等待处理 |
| `processing` | 正在处理（提取中） |
| `completed` | 处理完成 |
| `failed` | 处理失败 |

---

## 下载文件

### 下载到内存

```python
content = client.files.download(file_id="f_abc123")

# 保存到本地
with open("downloaded.pdf", "wb") as f:
    f.write(content)
```

### 获取下载 URL

```python
# 获取预签名 URL（有效期 1 小时）
url = client.files.get_download_url(file_id="f_abc123")
print(url)  # https://storage.unifiles.dev/...
```

### REST API 下载

```bash
# 直接下载
curl -X GET "https://api.unifiles.dev/v1/files/f_abc123/download" \
  -H "Authorization: Bearer sk_..." \
  -o downloaded.pdf
```

---

## 更新文件元数据

```python
# 更新标签
file = client.files.update(
    file_id="f_abc123",
    tags=["legal", "reviewed", "2024"]
)

# 更新元数据
file = client.files.update(
    file_id="f_abc123",
    metadata={
        "reviewed_by": "john",
        "reviewed_at": "2024-01-15"
    }
)
```

---

## 删除文件

### 删除单个文件

```python
client.files.delete(file_id="f_abc123")
```

### 批量删除

```python
file_ids = ["f_abc123", "f_def456", "f_ghi789"]

for file_id in file_ids:
    client.files.delete(file_id)
```

!!! warning "注意"
    删除文件会同时删除相关的提取结果和知识库中的文档索引。此操作不可逆。

---

## 最佳实践

### 1. 使用有意义的标签

```python
# ❌ 不好的标签
file = client.files.upload("contract.pdf", tags=["file1"])

# ✅ 好的标签
file = client.files.upload("contract.pdf", tags=[
    "contract",
    "legal",
    "2024-Q1",
    "project:merger"
])
```

### 2. 添加结构化元数据

```python
file = client.files.upload(
    path="report.pdf",
    metadata={
        "document_type": "quarterly_report",
        "fiscal_year": 2024,
        "quarter": "Q1",
        "department": "finance",
        "author": "john.doe@company.com",
        "classification": "internal"
    }
)
```

### 3. 处理上传错误

```python
from unifiles.exceptions import (
    UnifilesError,
    ValidationError,
    FileTooLargeError
)

try:
    file = client.files.upload("large_file.pdf")
except FileTooLargeError as e:
    print(f"文件太大: {e.size} > {e.limit}")
except ValidationError as e:
    print(f"文件格式不支持: {e.message}")
except UnifilesError as e:
    print(f"上传失败: {e.message}")
```

### 4. 检查文件是否存在

```python
def file_exists(client, file_id):
    try:
        client.files.get(file_id)
        return True
    except NotFoundError:
        return False
```

---

## 常见问题

??? question "上传大文件时超时怎么办？"

    增加超时时间：
    
    ```python
    client = UnifilesClient(
        api_key="sk_...",
        timeout=300  # 5 分钟
    )
    ```
    
    或者分块上传（即将支持）。

??? question "如何检查文件是否已存在？"

    使用文件哈希检查去重：
    
    ```python
    import hashlib
    
    def get_file_hash(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    # 检查是否已上传
    file_hash = get_file_hash("document.pdf")
    existing = client.files.list(file_hash=file_hash)
    
    if existing.items:
        print("文件已存在:", existing.items[0].id)
    else:
        file = client.files.upload("document.pdf")
    ```

??? question "如何批量上传文件？"

    ```python
    from pathlib import Path
    
    folder = Path("documents")
    files = []
    
    for path in folder.glob("*.pdf"):
        file = client.files.upload(str(path))
        files.append(file)
        print(f"已上传: {path.name} -> {file.id}")
    
    print(f"共上传 {len(files)} 个文件")
    ```

---

## 下一步

<div class="grid cards" markdown>

-   :material-text-recognition: **内容提取**
    
    对上传的文件进行 OCR 和内容提取
    
    [:octicons-arrow-right-24: content-extraction.md](./content-extraction.md)

-   :material-database-search: **知识库**
    
    将文件内容索引到知识库
    
    [:octicons-arrow-right-24: knowledge-bases.md](./knowledge-bases.md)

</div>
