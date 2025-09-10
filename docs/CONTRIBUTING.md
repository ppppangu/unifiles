# 🤝 贡献指南

感谢你对 File Server 项目的关注！我们欢迎任何形式的贡献。

## 🚀 快速开始

### 环境搭建

```bash
# 1. Fork 并克隆项目
git clone https://github.com/your-username/file_server.git
cd file_server

# 2. 安装开发依赖
pip install -e ".[dev]"

# 3. 启动开发服务
docker-compose -f docker-compose.dev.yml up -d
uvicorn server.app.v1.main:app --reload --port 8088
```

## 📋 贡献类型

### 🐛 Bug报告
- 使用 [Bug Report](https://github.com/your-repo/issues/new?template=bug_report.md) 模板
- 提供详细的复现步骤
- 包含错误日志和环境信息

### ✨ 功能建议
- 使用 [Feature Request](https://github.com/your-repo/issues/new?template=feature_request.md) 模板
- 说明使用场景和预期效果
- 考虑向后兼容性

### 📚 文档改进
- 修正错别字、链接错误
- 补充使用示例
- 翻译文档

### 🛠️ 代码贡献
- 新功能开发
- Bug修复
- 性能优化
- 测试覆盖

## 🔧 开发流程

### 1. 创建分支

```bash
# 功能分支
git checkout -b feature/your-feature-name

# 修复分支
git checkout -b fix/issue-description

# 文档分支
git checkout -b docs/update-readme
```

### 2. 编写代码

#### 代码规范
```python
# ✅ 良好的代码示例
async def upload_file(
    file: UploadFile,
    user_id: str
) -> FileUploadResponse:
    """
    上传文件到存储系统
    
    Args:
        file: 上传的文件对象
        user_id: 用户ID
        
    Returns:
        FileUploadResponse: 上传结果
        
    Raises:
        HTTPException: 文件验证失败时
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    return await file_service.process_upload(file, user_id)
```

#### 类型注解
```python
from typing import Dict, List, Optional, Union

# 使用明确的类型注解
def process_documents(
    documents: List[Dict[str, Any]],
    options: Optional[Dict[str, Union[str, int]]] = None
) -> List[ProcessedDocument]:
    # 实现逻辑
    pass
```

### 3. 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api.py::test_upload_file

# 测试覆盖率
pytest --cov=server --cov-report=html
```

#### 测试示例
```python
@pytest.mark.asyncio
async def test_upload_file_success():
    """测试文件上传成功场景"""
    with TestClient(app) as client:
        with open("test_files/sample.pdf", "rb") as f:
            response = client.post(
                "/files",
                files={"file": ("sample.pdf", f, "application/pdf")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "file_id" in data["file"]
```

### 4. 提交代码

#### 提交信息格式
```
类型(范围): 简短描述

详细说明（可选）

- 变更点1
- 变更点2

Closes #123
```

**类型标识**:
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建工具

**示例**:
```bash
git commit -m "feat(api): add file batch upload endpoint

- Support multiple file upload in single request
- Add validation for total file size limit
- Update API documentation

Closes #45"
```

### 5. 创建Pull Request

#### PR标题格式
```
类型: 简短描述 (#issue号)
```

#### PR描述模板
```markdown
## 📋 变更说明
简述本次PR的主要变更内容

## 🎯 解决的问题
- 修复了什么问题
- 添加了什么功能
- Closes #123

## 🧪 测试计划
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试完成

## 📸 截图（如适用）
贴出相关截图

## ✅ 检查清单
- [ ] 代码遵循项目规范
- [ ] 添加了必要的测试
- [ ] 文档已更新
- [ ] CI检查通过
```

## 🧩 架构指南

### 添加新的API端点

```python
# 1. 在 server/app/v1/main.py 添加路由
@app.post("/files/{file_id}/analyze", tags=["Files"])
async def analyze_file(
    request: Request,
    file_id: str,
    analysis_type: str = "basic"
):
    user_id = request.state.user_id
    # 业务逻辑
    return {"result": "analysis complete"}
```

### 添加新的数据模型

```python
# server/core/database/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class AnalysisResult:
    file_id: str
    analysis_type: str
    result: dict
    created_at: Optional[str] = None
```

### 添加新的服务组件

```python
# server/core/services/analysis_service.py
class AnalysisService:
    def __init__(self, config: dict):
        self.config = config
    
    async def analyze_file(
        self, 
        file_path: str, 
        analysis_type: str
    ) -> dict:
        # 分析逻辑实现
        return {"status": "completed"}
```

### 扩展中间件

```python
# server/app/v1/middlewares.py
class CustomMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # 中间件逻辑
        await self.app(scope, receive, send)

# 在 main.py 中注册
app.add_middleware(CustomMiddleware)
```

## 🧪 测试指南

### 单元测试
```python
# tests/unit/test_file_service.py
def test_validate_file_extension():
    service = FileService()
    
    # 测试支持的格式
    assert service.validate_extension("document.pdf") is True
    
    # 测试不支持的格式
    assert service.validate_extension("malware.exe") is False
```

### 集成测试
```python
# tests/integration/test_api_endpoints.py
@pytest.mark.asyncio
async def test_file_upload_workflow():
    """测试完整的文件上传工作流"""
    # 上传文件
    upload_response = await client.post("/files", ...)
    file_id = upload_response.json()["file"]["file_id"]
    
    # 处理文档
    process_response = await client.post(
        f"/knowledge-bases/test/documents",
        json={"file_id": file_id}
    )
    
    # 验证结果
    assert process_response.status_code == 200
```

## 📝 文档规范

### API文档
```python
@app.post("/files", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件到存储系统
    
    支持的文件格式：
    - 文档：PDF, DOC, DOCX, TXT
    - 图片：JPG, PNG, GIF
    - 表格：XLS, XLSX, CSV
    
    限制：
    - 最大文件大小：100MB
    - 并发上传限制：5个文件
    
    Returns:
        FileUploadResponse: 包含文件ID和访问URL
    """
```

### 代码注释
```python
class DocumentProcessor:
    """
    文档处理器
    
    负责协调文档的格式转换、OCR处理和向量化存储
    支持可插拔的OCR提供者
    """
    
    def __init__(self, ocr_provider: OCRProvider):
        """
        初始化文档处理器
        
        Args:
            ocr_provider: OCR服务提供者实例
        """
        self.ocr_provider = ocr_provider
    
    async def process(self, file_url: str) -> ProcessResult:
        """
        处理单个文档
        
        执行步骤：
        1. 下载并验证文件
        2. 转换为PDF格式
        3. 执行OCR识别
        4. 向量化存储
        
        Args:
            file_url: 待处理文件的URL
            
        Returns:
            ProcessResult: 处理结果，包含状态和生成的文件URL
            
        Raises:
            ValidationError: 文件格式不支持
            ProcessingError: 处理过程中出现错误
        """
```

## 🚀 发布流程

### 版本号规范
遵循 [语义化版本](https://semver.org/lang/zh-CN/)：
- `1.0.0` - 主版本号.次版本号.修订号
- `1.0.0-alpha.1` - 预发布版本

### 发布检查清单
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] CHANGELOG已更新
- [ ] 版本号已更新
- [ ] 创建发布标签

```bash
# 更新版本
bump2version minor  # 或 major/patch

# 生成变更日志
git-changelog -o CHANGELOG.md

# 创建标签
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin main --tags
```

## 🛡️ 安全考虑

### 代码审查重点
- SQL注入防护
- 文件上传安全
- 用户输入验证
- 敏感信息保护

### 安全测试
```python
def test_sql_injection_protection():
    """测试SQL注入防护"""
    malicious_input = "'; DROP TABLE users; --"
    
    with pytest.raises(ValidationError):
        validate_user_id(malicious_input)

def test_file_upload_security():
    """测试文件上传安全"""
    # 测试危险文件类型
    dangerous_file = ("malware.exe", b"executable_content")
    
    response = client.post("/files", files={"file": dangerous_file})
    assert response.status_code == 400
```

## ❓ 常见问题

### Q: 如何调试API？
```bash
# 启用调试模式
LOG_LEVEL=DEBUG uvicorn server.app.v1.main:app --reload

# 查看日志
tail -f server/app/v1/logs/$(date +%Y-%m-%d).log
```

### Q: 如何添加新的OCR提供者？
```python
# 1. 实现OCRProvider接口
class CustomOCRProvider:
    async def extract_text_from_pdf(self, pdf_url: str) -> str:
        # 实现OCR逻辑
        return extracted_text

# 2. 注册到系统
# 在配置中添加provider配置
```

### Q: 如何运行特定测试？
```bash
# 运行单个测试文件
pytest tests/test_api.py

# 运行单个测试函数
pytest tests/test_api.py::test_upload_file

# 运行特定标记的测试
pytest -m "not slow"
```

## 📞 获取帮助

- 💬 **讨论**: [GitHub Discussions](https://github.com/your-repo/discussions)
- 🐛 **Bug报告**: [GitHub Issues](https://github.com/your-repo/issues)
- 📧 **邮件**: dev@yourproject.com
- 💬 **社区**: [Discord/Slack链接]

---

**🙏 感谢你的贡献！** 每一个PR都让项目变得更好。