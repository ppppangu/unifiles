# 理解 Markdown 输出

本教程解释为什么 Unifiles 选择 Markdown 作为统一输出格式，以及如何最大化利用这一设计。

## 为什么是 Markdown？

### 问题：格式碎片化

传统的文档处理系统面临一个共同挑战：

```
PDF → PDF解析器 → 自定义JSON结构
Word → Word解析器 → 另一种JSON结构
图片 → OCR引擎 → 纯文本
HTML → HTML解析器 → 又一种结构
```

每种格式产生不同的输出结构，下游应用需要处理多种情况。

### 解决方案：Markdown 作为单一真实来源

Unifiles 采用 **Markdown-as-SSOT** (Single Source of Truth) 设计：

```
PDF  ─┐
Word ─┤
图片 ─┼──→ Unifiles ──→ Markdown ──→ 你的应用
HTML ─┤
...  ─┘
```

**所有格式，统一输出**。你的应用只需处理一种格式。

## Markdown 的优势

### 1. LLM 友好

大语言模型对 Markdown 有天然的理解能力：

```python
# Markdown 输入
context = """
# 合同条款

## 第一条 合同目的
本合同旨在...

## 第二条 违约责任
如一方违约，应支付违约金...
"""

# LLM 能清晰理解文档结构
prompt = f"基于以下合同内容回答问题：\n{context}\n\n问题：违约金如何计算？"
```

### 2. 人类可读

无需专门的阅读器，任何文本编辑器都能查看：

```markdown
# 财务报告 2024

## 第一季度

| 指标 | 数值 | 同比 |
|-----|------|------|
| 营收 | 1000万 | +15% |
| 利润 | 200万 | +20% |

## 分析

第一季度业绩超预期，主要得益于...
```

### 3. 结构化但灵活

保留文档结构，同时足够灵活：

```markdown
# 标题（一级）
## 章节（二级）
### 小节（三级）

段落文本...

- 列表项1
- 列表项2

| 表头1 | 表头2 |
|-------|-------|
| 数据1 | 数据2 |

> 引用块

**强调** 和 *斜体*
```

### 4. 轻量级

相比 HTML 或 JSON，Markdown 更紧凑：

```
# HTML: 复杂
<html><body><h1>标题</h1><p>段落</p></body></html>

# JSON: 冗长
{"type":"document","children":[{"type":"heading","level":1,"text":"标题"},{"type":"paragraph","text":"段落"}]}

# Markdown: 简洁
# 标题
段落
```

### 5. 易于转换

Markdown 可以轻松转换为其他格式：

```python
import markdown
from markdown import markdown as md_to_html

# Markdown → HTML
html = md_to_html(extraction.markdown)

# Markdown → 纯文本
text = extraction.markdown  # 本身就是文本

# Markdown → PDF（使用第三方库）
# from md2pdf import md2pdf
```

## 输出结构解析

### 标准输出格式

Unifiles 的 Markdown 输出遵循一致的结构：

```markdown
# 文档标题

## 第一章

这是正文内容。包含各种信息...

### 1.1 小节

更详细的内容...

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A | B | C |

## 第二章

更多内容...

---

<!-- unifiles-metadata
file_id: file_abc123
pages: 15
extracted_at: 2024-01-15T10:30:00Z
-->
```

### 元数据注释

提取结果末尾包含元数据注释：

```python
extraction = client.extractions.get(extraction_id)

# 获取纯内容（不含元数据）
content = extraction.markdown

# 元数据通过属性访问
print(extraction.file_id)
print(extraction.total_pages)
print(extraction.completed_at)
```

## 实际应用示例

### 示例1：构建问答系统

```python
from unifiles import UnifilesClient
from openai import OpenAI

unifiles = UnifilesClient(api_key="sk_unifiles_...")
openai = OpenAI(api_key="sk_openai_...")

# 1. 上传并提取文档
file = unifiles.files.upload("company_policy.pdf")
extraction = unifiles.extractions.create(file_id=file.id)
extraction.wait()

# 2. Markdown 内容直接用于 LLM
def answer_question(question: str, context: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "基于提供的文档回答问题。"},
            {"role": "user", "content": f"文档内容：\n{context}\n\n问题：{question}"}
        ]
    )
    return response.choices[0].message.content

# 3. 使用
answer = answer_question(
    "年假政策是什么？",
    extraction.markdown
)
print(answer)
```

### 示例2：文档摘要

```python
def summarize_document(markdown_content: str) -> str:
    """利用 Markdown 结构生成摘要"""
    
    # Markdown 的标题结构帮助 LLM 理解文档框架
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "你是文档摘要专家。根据 Markdown 文档的结构生成摘要。"
            },
            {
                "role": "user",
                "content": f"请为以下文档生成摘要：\n\n{markdown_content}"
            }
        ]
    )
    return response.choices[0].message.content

summary = summarize_document(extraction.markdown)
```

### 示例3：提取特定章节

```python
import re

def extract_section(markdown: str, heading: str) -> str:
    """从 Markdown 中提取特定章节"""
    
    # 匹配章节标题和内容
    pattern = rf"(^#{1,6}\s+{re.escape(heading)}.*?)(?=^#{1,6}\s|\Z)"
    match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
    
    if match:
        return match.group(1).strip()
    return ""

# 只提取"违约责任"章节
liability_section = extract_section(extraction.markdown, "违约责任")
print(liability_section)
```

### 示例4：表格提取

```python
import re
import pandas as pd

def extract_tables(markdown: str) -> list:
    """从 Markdown 中提取所有表格"""
    
    # 匹配 Markdown 表格
    table_pattern = r'\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)'
    matches = re.findall(table_pattern, markdown)
    
    tables = []
    for header, rows in matches:
        # 解析表头
        headers = [h.strip() for h in header.split('|') if h.strip()]
        
        # 解析数据行
        data = []
        for row in rows.strip().split('\n'):
            cells = [c.strip() for c in row.split('|') if c.strip()]
            data.append(cells)
        
        # 转为 DataFrame
        df = pd.DataFrame(data, columns=headers)
        tables.append(df)
    
    return tables

tables = extract_tables(extraction.markdown)
for i, df in enumerate(tables):
    print(f"表格 {i+1}:")
    print(df)
    print()
```

## 处理不同文档类型

### PDF 文档

```markdown
# 原始 PDF 结构
├── 封面
├── 目录
├── 正文章节
└── 附录

# Markdown 输出
# 文档标题

## 目录
- 第一章
- 第二章
...

## 第一章
正文内容...
```

### Word 文档

```markdown
# 原始 Word 样式
├── 标题1 → # 一级标题
├── 标题2 → ## 二级标题
├── 正文   → 段落
└── 表格   → Markdown 表格
```

### 扫描件/图片

```markdown
# OCR 识别结果

识别出的文本内容...

<!-- 注：图片中的文字通过OCR识别 -->
```

### 电子表格

```markdown
# Sheet1

| A | B | C |
|---|---|---|
| 1 | 2 | 3 |
| 4 | 5 | 6 |

# Sheet2

| 列1 | 列2 |
|-----|-----|
| 数据 | 数据 |
```

## 最佳实践

### 1. 保持原始 Markdown

```python
# 推荐：保存原始 Markdown
with open("extracted.md", "w", encoding="utf-8") as f:
    f.write(extraction.markdown)

# 不推荐：立即转换为其他格式（损失灵活性）
```

### 2. 利用结构化特性

```python
# 利用标题层级进行智能分块
def smart_chunk_by_heading(markdown: str) -> list:
    """按标题分块，保持语义完整性"""
    chunks = re.split(r'(?=^#{1,3}\s)', markdown, flags=re.MULTILINE)
    return [chunk.strip() for chunk in chunks if chunk.strip()]
```

### 3. 配合向量搜索

```python
# Markdown 的分块更适合语义搜索
kb = client.knowledge_bases.create(
    name="docs",
    chunking_strategy={
        "type": "semantic",  # 利用 Markdown 结构
        "chunk_size": 512
    }
)
```

## 小结

Markdown-as-SSOT 设计带来的好处：

| 特性 | 好处 |
|-----|------|
| 统一格式 | 简化下游处理 |
| LLM 友好 | 提升 AI 理解能力 |
| 人类可读 | 便于调试和验证 |
| 结构化 | 支持智能分块 |
| 轻量级 | 减少存储和传输成本 |
| 可转换 | 灵活适配各种需求 |

## 下一步

- [三层架构入门](three-layers-primer.md) - 了解完整的处理流程
- [内容提取](../basics/extracting-content.md) - 实践提取操作
- [分块策略详解](../intermediate/chunking-strategies.md) - 优化 Markdown 分块
