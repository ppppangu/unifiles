# 第一次上传

本教程将带你完成第一次文件上传，了解文件在 Unifiles 中的生命周期。

## 前置条件

- 已安装 Python SDK：`pip install unifiles-client`
- 已获取 API Key
- 准备一个测试文件（PDF、Word 或图片）

## 步骤 1：初始化客户端

```python
from unifiles import UnifilesClient

# 使用 API Key 初始化
client = UnifilesClient(api_key="sk_your_api_key")

# 或从环境变量读取
# export UNIFILES_API_KEY=sk_your_api_key
client = UnifilesClient()  # 自动读取 UNIFILES_API_KEY
```

## 步骤 2：上传文件

### 最简单的上传

```python
# 上传本地文件
file = client.files.upload("document.pdf")

print(f"上传成功！")
print(f"文件ID: {file.id}")
print(f"文件名: {file.filename}")
print(f"大小: {file.size} 字节")
print(f"类型: {file.content_type}")
```

**输出：**

```
上传成功！
文件ID: file_abc123xyz
文件名: document.pdf
大小: 1048576 字节
类型: application/pdf
```

### 带元数据的上传

```python
file = client.files.upload(
    path="contract.pdf",
    metadata={
        "project": "合同管理",
        "department": "法务部",
        "year": 2024
    },
    tags=["合同", "重要", "待审核"]
)

print(f"文件ID: {file.id}")
print(f"元数据: {file.metadata}")
print(f"标签: {file.tags}")
```

### 从内存上传

```python
# 从字节流上传
with open("document.pdf", "rb") as f:
    content = f.read()

file = client.files.upload(
    content=content,
    filename="uploaded_document.pdf",
    content_type="application/pdf"
)
```

## 步骤 3：查看文件信息

```python
# 通过 ID 获取文件信息
file = client.files.get(file_id="file_abc123xyz")

print(f"文件名: {file.filename}")
print(f"大小: {file.size / 1024:.2f} KB")
print(f"类型: {file.content_type}")
print(f"创建时间: {file.created_at}")
print(f"元数据: {file.metadata}")
print(f"标签: {file.tags}")
```

## 步骤 4：列出文件

```python
# 列出所有文件
files = client.files.list()

print(f"共有 {files.total} 个文件")
for f in files.items:
    print(f"  - {f.id}: {f.filename} ({f.size} bytes)")
```

### 带过滤的列表

```python
# 按标签过滤
files = client.files.list(tags=["合同"])

# 分页
files = client.files.list(limit=10, offset=0)

# 按时间排序
files = client.files.list(sort_by="created_at", order="desc")
```

## 步骤 5：下载文件

```python
# 获取文件内容
content = client.files.download(file_id="file_abc123xyz")

# 保存到本地
with open("downloaded.pdf", "wb") as f:
    f.write(content)

print("文件已下载")
```

## 步骤 6：删除文件

```python
# 删除单个文件
client.files.delete(file_id="file_abc123xyz")
print("文件已删除")

# 注意：删除文件会级联删除相关的提取结果和知识库文档
```

## 文件生命周期

```
创建 → 存储 → 使用 → 删除

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  上传   │ ──► │  存储   │ ──► │  使用   │ ──► │  删除   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │
     ▼               ▼               ▼               ▼
  验证格式        安全存储       提取/索引       级联清理
  计算哈希        生成ID         搜索查询       释放空间
  检查大小        记录元数据     下载访问
```

## 完整示例

```python
from unifiles import UnifilesClient
from unifiles.exceptions import ValidationError, NotFoundError

def upload_and_manage_file():
    """完整的文件管理流程"""
    
    client = UnifilesClient(api_key="<api-key>")
    
    # 1. 上传文件
    print("正在上传文件...")
    try:
        file = client.files.upload(
            path="sample.pdf",
            metadata={"source": "demo", "version": "1.0"},
            tags=["示例", "测试"]
        )
        print(f"✓ 上传成功: {file.id}")
    except ValidationError as e:
        print(f"✗ 上传失败: {e.message}")
        return
    
    # 2. 验证上传
    print("\n正在验证...")
    retrieved = client.files.get(file.id)
    print(f"✓ 文件名: {retrieved.filename}")
    print(f"✓ 大小: {retrieved.size} bytes")
    print(f"✓ 类型: {retrieved.content_type}")
    
    # 3. 列出文件
    print("\n当前文件列表:")
    files = client.files.list(limit=5)
    for f in files.items:
        print(f"  - {f.filename} ({f.id})")
    
    # 4. 下载验证
    print("\n正在下载验证...")
    content = client.files.download(file.id)
    print(f"✓ 下载完成: {len(content)} bytes")
    
    # 5. 可选：删除文件
    # print("\n正在删除...")
    # client.files.delete(file.id)
    # print("✓ 删除成功")
    
    return file

# 运行
file = upload_and_manage_file()
```

## 支持的文件格式

| 格式 | 扩展名 | MIME 类型 |
|-----|--------|----------|
| PDF | `.pdf` | `application/pdf` |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Word (旧) | `.doc` | `application/msword` |
| Excel | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| PowerPoint | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| 纯文本 | `.txt` | `text/plain` |
| Markdown | `.md` | `text/markdown` |
| HTML | `.html` | `text/html` |
| PNG | `.png` | `image/png` |
| JPEG | `.jpg`, `.jpeg` | `image/jpeg` |

## 文件大小限制

| 套餐 | 单文件最大 | 总存储 |
|-----|-----------|-------|
| 免费版 | 10 MB | 1 GB |
| 专业版 | 100 MB | 100 GB |
| 企业版 | 500 MB | 无限制 |

## 常见问题

### Q: 上传同名文件会覆盖吗？

**A:** 不会。每次上传都会创建新的文件记录，生成新的 ID。

```python
file1 = client.files.upload("doc.pdf")  # file_abc
file2 = client.files.upload("doc.pdf")  # file_xyz（新ID）
```

### Q: 如何更新文件？

**A:** 上传新版本，然后删除旧版本。

```python
# 上传新版本
new_file = client.files.upload("doc_v2.pdf")

# 删除旧版本
client.files.delete(old_file_id)
```

### Q: 上传失败怎么办？

**A:** 检查文件格式、大小和网络连接。

```python
from unifiles.exceptions import ValidationError, UnifilesError

try:
    file = client.files.upload("document.xyz")
except ValidationError as e:
    if e.code == "UNSUPPORTED_FORMAT":
        print("不支持的文件格式")
    elif e.code == "FILE_TOO_LARGE":
        print("文件过大")
except UnifilesError as e:
    print(f"上传失败: {e.message}")
```

## 下一步

文件上传成功后，你可以：

- [内容提取](extracting-content.md) - 从文件中提取结构化内容
- [构建知识库](building-knowledge-base.md) - 将文件加入知识库实现搜索
- [元数据与标签](../intermediate/custom-metadata.md) - 更高级的文件组织方式
