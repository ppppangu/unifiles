# Extractions 命名空间

内容提取操作。

## create

创建提取任务。

```python
extraction = client.extractions.create(
    file_id: str,
    mode: str = "normal",
    options: dict = None
) -> Extraction
```

### 参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `file_id` | str | 文件 ID |
| `mode` | str | `simple`、`normal`、`advanced` |
| `options` | dict | 提取选项 |

### 示例

```python
# 基本提取
extraction = client.extractions.create(file_id="file_abc123")

# 高级提取
extraction = client.extractions.create(
    file_id="file_abc123",
    mode="advanced",
    options={"language": "zh", "ocr_provider": "default"}
)

# 等待完成
extraction = extraction.wait(timeout=300)
print(extraction.markdown)
```

---

## get

获取提取结果。

```python
extraction = client.extractions.get(extraction_id: str) -> Extraction
```

### 示例

```python
extraction = client.extractions.get("ext_xyz789")
if extraction.status == "completed":
    print(extraction.markdown)
```

---

## list

获取文件的提取记录。

```python
extractions = client.extractions.list(
    file_id: str,
    limit: int = 50,
    offset: int = 0
) -> ExtractionList
```

---

## Extraction 对象

```python
@dataclass
class Extraction:
    id: str                    # 提取 ID
    file_id: str               # 文件 ID
    status: str                # pending | processing | completed | failed
    mode: str                  # 提取模式
    progress: int              # 进度 (0-100)
    markdown: str              # 提取内容
    total_pages: int           # 总页数
    metadata: dict             # 文档元信息
    error: dict                # 错误信息
    created_at: datetime
    completed_at: datetime

    def wait(self, timeout: int = 300) -> "Extraction":
        """等待提取完成"""
        pass
```

### wait 方法

```python
# 同步等待
extraction = extraction.wait(timeout=300)

if extraction.status == "completed":
    print(f"提取成功: {extraction.total_pages} 页")
elif extraction.status == "failed":
    print(f"提取失败: {extraction.error}")
```
