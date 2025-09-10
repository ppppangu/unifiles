# 📚 文档索引

欢迎来到 File Server Core 文档中心！这里提供了完整的开发和使用指南。

## 🚀 快速导航

### 新手入门
- **[快速开始](QUICK_START.md)** - 5分钟部署指南，快速上手
- **[API 参考](API_REFERENCE.md)** - 完整的API接口文档

### 开发者资源
- **[开发文档](DEVELOPMENT.md)** - 架构说明、模块使用、开发指南
- **[示例代码](../examples/)** - 实际使用示例

## 📋 文档概览

| 文档 | 描述 | 适合人群 |
|------|------|----------|
| [QUICK_START.md](QUICK_START.md) | 快速部署和基本使用 | 运维、新用户 |
| [API_REFERENCE.md](API_REFERENCE.md) | REST API和Python SDK详细说明 | 前端开发者、集成开发者 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 架构设计、开发指南、扩展说明 | 后端开发者、贡献者 |

## 🏗️ 项目架构概览

```
File Server Core
├── 🎯 OCR模块 - 可插拔的文档识别系统
│   ├── Mistral OCR (已实现)
│   └── 其他供应商 (可扩展)
├── 💾 存储模块 - MinIO + 向量数据库
├── 🕸️ 图谱模块 - 知识图谱生成与查询
├── 🔧 工具模块 - 配置管理、文件处理
└── 🚀 FastAPI - REST API服务
```

## ⚡ 核心特性

- ✅ **可插拔OCR架构** - 支持多个OCR供应商
- ✅ **异步处理** - 高性能文档处理
- ✅ **企业级存储** - MinIO对象存储 + PostgreSQL向量数据库
- ✅ **知识图谱** - 自动生成文档关系图谱
- ✅ **PyPI包** - 可独立使用的Python库
- ✅ **完整API** - RESTful接口，支持多种文件格式
- ✅ **向后兼容** - 现有代码无缝迁移

## 🔧 支持的功能

### 文件格式支持
- **文档**: Word, PowerPoint, Excel, OpenOffice
- **文本**: TXT, Markdown, CSV, HTML, XML  
- **图像**: PNG, JPG, TIFF, BMP
- **PDF**: 完整PDF处理支持
- **代码**: Python, JavaScript, JSON, Jupyter Notebook

### OCR识别能力
- **Mistral OCR** - 高精度文档识别
- **批量处理** - 并发处理多个文档
- **结果持久化** - Markdown + 图片保存
- **可扩展架构** - 轻松添加其他OCR服务

### 存储和检索
- **对象存储** - MinIO高性能文件存储
- **向量数据库** - PostgreSQL + pgvector语义检索
- **知识图谱** - 文档关系自动发现

## 📊 使用场景

1. **文档管理系统** - 企业文档数字化和管理
2. **知识库建设** - 自动化知识提取和组织
3. **内容分析平台** - 大规模文档分析和洞察
4. **AI应用开发** - 为LLM提供文档理解能力
5. **数字化转型** - 传统文档向数字化转换

## 🎯 快速开始

### 1. 最简单的开始方式
```bash
# 克隆项目
git clone <repo-url> && cd file_server

# 安装依赖
pip install -e .

# 启动服务
uvicorn main:app --reload
```

### 2. Python SDK使用
```python
from file_server_core.ocr import OCRProcessor

# OCR文档识别
processor = OCRProcessor('mistral')
text = await processor.aprocess_file('document.pdf')
```

### 3. REST API调用
```bash
# 上传文件
curl -X POST "http://localhost:8087/upload_minio" \
  -F "upload_file=@document.pdf"

# 处理文档  
curl -X POST "http://localhost:8087/process" \
  -d "user_id=test&file_url=http://example.com/file.pdf"
```

## 📈 性能指标

- **OCR处理速度**: ~2-5秒/页（取决于复杂度）
- **并发处理**: 支持5个并发OCR任务
- **文件大小限制**: 10MB/文件（OCR），无限制（存储）
- **支持格式**: 15+种文档格式

## 🛠️ 开发环境要求

- **Python**: 3.8+
- **数据库**: PostgreSQL 12+ (with pgvector)
- **对象存储**: MinIO或兼容S3的存储
- **OCR服务**: Mistral API密钥（可选）

## 📞 获取帮助

### 文档导航
- 🚀 **快速上手**: [QUICK_START.md](QUICK_START.md)
- 🔍 **API查询**: [API_REFERENCE.md](API_REFERENCE.md)  
- 🛠️ **深度开发**: [DEVELOPMENT.md](DEVELOPMENT.md)

### 实用工具
```bash
# CLI健康检查
python -m file_server_core.cli --health

# 查看支持的OCR供应商
python -c "from file_server_core.ocr import OCRProcessor; print(OCRProcessor('mistral').get_supported_providers())"

# 运行示例代码
python examples/basic_usage.py
```

### 社区支持
- 🐛 **问题报告**: 提交 GitHub Issues
- 💬 **功能建议**: 参与 Discussions  
- 🤝 **贡献代码**: 查看 [DEVELOPMENT.md](DEVELOPMENT.md) 贡献指南

---

📝 **文档更新**: 这些文档会随着项目发展持续更新，建议收藏本页面以获取最新信息。