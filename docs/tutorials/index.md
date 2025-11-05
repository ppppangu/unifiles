# Tutorials

欢迎来到 Unifiles 教程！这里提供从基础到高级的系列教程，帮助您快速上手并深入掌握 Unifiles。

## 学习路径

### 🎯 初学者路径（第1-2周）

如果您是第一次使用 Unifiles，建议按照以下顺序学习：

1. **环境搭建**
   - 安装 Python 和 uv
   - 配置数据库和依赖服务
   - 启动 Unifiles 服务

   [查看教程](../quickstart.md)

2. **第一个文件上传**
   - 使用 API 上传文件
   - 查看文件元数据
   - 下载文件

   [查看教程（待补充）]

3. **内容提取**
   - 触发 OCR 提取
   - 查看提取结果
   - 理解 Markdown 格式

   [查看教程（待补充）]

4. **基础搜索**
   - 创建知识库
   - 添加文档
   - 执行搜索查询

   [查看教程（待补充）]

### 🚀 进阶路径（第3-4周）

掌握基础后，可以学习更高级的功能：

1. **API 集成**
   - 使用 Python SDK
   - 批量文件处理
   - 错误处理

   [查看教程（待补充）]

2. **自定义处理流程**
   - 配置处理流水线
   - 自定义处理器
   - 处理钩子

   [查看教程（待补充）]

3. **批量操作**
   - 批量上传
   - 批量提取
   - 批量索引

   [查看教程（待补充）]

### 🏆 高级路径（第5+周）

深入理解系统原理和高级特性：

1. **自定义流水线**
   - 实现自定义处理阶段
   - 流水线编排
   - 性能优化

   [查看教程（待补充）]

2. **高级分块策略**
   - 语义分块
   - 层次化分块
   - 自定义分块算法

   [查看教程（待补充）]

3. **性能调优**
   - 数据库优化
   - 缓存策略
   - 并发控制

   [查看教程（待补充）]

## 按功能分类

### 文件管理
- [文件上传](../features.md#第一层文件管理)
- [文件下载](../features.md#第一层文件管理)
- [文件元数据管理](../features.md#第一层文件管理)

### 内容提取
- [OCR 文本提取](../features.md#第二层内容提取)
- [格式转换](../features.md#第二层内容提取)
- [内容结构化](../features.md#第二层内容提取)

### 知识库
- [知识库创建](../features.md#第三层知识库管理)
- [文档索引](../features.md#第三层知识库管理)
- [向量搜索](../features.md#第三层知识库管理)

## 实践项目

### 项目 1：文档搜索引擎
构建一个简单的文档搜索引擎，支持：
- PDF 文件上传
- 自动内容提取
- 语义搜索

[项目指南（待补充）]

### 项目 2：智能问答系统
基于 Unifiles 构建一个问答系统，支持：
- 多文档上传
- 自动知识库构建
- 基于上下文的问答

[项目指南（待补充）]

### 项目 3：文档分析平台
开发一个文档分析平台，支持：
- 批量文档处理
- 内容摘要生成
- 关键信息提取

[项目指南（待补充）]

## 常见场景

### 场景 1：企业文档管理
- 上传公司内部文档
- 建立部门知识库
- 快速搜索和检索

### 场景 2：学术论文整理
- 导入 PDF 论文
- 提取关键信息
- 文献引用管理

### 场景 3：法律文件分析
- 上传法律文档
- OCR 识别
- 条款检索

## 视频教程

[视频教程即将推出]

## 示例代码

### Python 示例

```python
from unifiles_client import UnifilesClient

# 初始化客户端
client = UnifilesClient(api_key="[REDACTED]")

# 上传文件
file = client.files.upload("document.pdf")
print(f"File uploaded: {file.id}")

# 提取内容
task = client.processors.extract(file.id)
result = task.wait()
print(f"Extraction completed: {result.markdown_content[:100]}...")

# 创建知识库
kb = client.knowledge_bases.create("My Knowledge Base")

# 添加文档
kb.add_document(file.id)

# 搜索
results = kb.search("What is this document about?", top_k=5)
for result in results:
    print(f"- {result.content[:100]}... (score: {result.score})")
```

### cURL 示例

```bash
# 上传文件
curl -X POST http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@document.pdf"

# 提取内容
curl -X POST http://localhost:8088/api/v1/processors/extract \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID"}'

# 创建知识库
curl -X POST http://localhost:8088/api/v1/knowledge-bases \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Knowledge Base"}'

# 搜索
curl -X POST http://localhost:8088/api/v1/knowledge-bases/KB_ID/search \
  -H "Authorization: Bearer [REDACTED]" \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "top_k": 5}'
```

## 疑难解答

### 常见问题

**Q: 文件上传失败怎么办？**
A: 检查文件大小是否超过限制（默认100MB），文件格式是否支持。

**Q: OCR 识别效果不好怎么办？**
A: 确保图片清晰度足够，可以尝试调整 DPI 设置。

**Q: 搜索结果不准确怎么办？**
A: 尝试调整分块策略，使用更合适的 embedding 模型。

[更多 FAQ](../faq.md)

## 社区贡献

我们欢迎社区贡献教程！如果您有好的教程想要分享：

1. Fork 项目仓库
2. 在 `docs/tutorials/` 下创建教程
3. 提交 Pull Request

[贡献指南](../CONTRIBUTING.md)

## 反馈

如果您在学习过程中遇到问题或有改进建议，欢迎：

- 提交 [GitHub Issue](https://github.com/ppppangu/Unifiles/issues)
- 加入讨论组
- 发送邮件至 support@unifiles.dev

## 下一步

- [快速开始](../quickstart.md) - 立即开始使用 Unifiles
- [API 文档](../api-reference.md) - 查看完整的 API 参考
- [开发指南](../CONTRIBUTING.md) - 参与 Unifiles 开发
