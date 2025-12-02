# Files 命名空间

文件管理操作。

## upload

上传文件。

```python
file = client.files.upload(
    path: str,
    content: bytes = None,
    filename: str = None,
    content_type: str = None,
    metadata: dict = None,
    tags: list = None
) -> File
```

### 参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `path` | str | 文件路径 |
| `content` | bytes | 文件内容（与 path 二选一） |
| `filename` | str | 文件名（使用 content 时必需） |
| `content_type` | str | MIME 类型 |
| `metadata` | dict | 自定义元数据 |
| `tags` | list | 标签列表 |

### 示例

```python
# 从路径上传
file = client.files.upload("document.pdf")

# 带元数据上传
file = client.files.upload(
    path="contract.pdf",
    metadata={"project": "legal", "year": 2024},
    tags=["contract", "important"]
)

# 从内存上传
with open("doc.pdf", "rb") as f:
    content = f.read()

file = client.files.upload(
    content=content,
    filename="uploaded.pdf",
    content_type="application/pdf"
)
```

---

## list

列出文件。

```python
files = client.files.list(
    limit: int = 50,
    offset: int = 0,
    tags: list = None,
    content_type: str = None,
    sort_by: str = "created_at",
    order: str = "desc"
) -> FileList
```

### 示例

```python
# 获取所有文件
files = client.files.list()
for f in files.items:
    print(f"{f.id}: {f.filename}")

# 按标签过滤
files = client.files.list(tags=["contract"])

# 分页
files = client.files.list(limit=20, offset=40)
```

---

## get

获取文件详情。

```python
file = client.files.get(file_id: str) -> File
```

### 示例

```python
file = client.files.get("file_abc123")
print(f"文件名: {file.filename}")
print(f"大小: {file.size}")
print(f"元数据: {file.metadata}")
```

---

## download

下载文件内容。

```python
content = client.files.download(file_id: str) -> bytes
```

### 示例

```python
content = client.files.download("file_abc123")

with open("downloaded.pdf", "wb") as f:
    f.write(content)
```

---

## delete

删除文件。

```python
client.files.delete(file_id: str) -> None
```

### 示例

```python
client.files.delete("file_abc123")
```

---

## File 对象

```python
@dataclass
class File:
    id: str                    # 文件 ID
    filename: str              # 文件名
    content_type: str          # MIME 类型
    size: int                  # 大小（字节）
    metadata: dict             # 元数据
    tags: list[str]            # 标签
    created_at: datetime       # 创建时间
    updated_at: datetime       # 更新时间
```
