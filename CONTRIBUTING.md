# 贡献指南

感谢您考虑为文件服务器项目做出贡献！本文档将指导您如何参与项目开发。

## 开始之前

### 环境准备
1. 确保安装了 Python 3.11+
2. 安装 `uv` 包管理器
3. 克隆项目到本地
4. 阅读 [开发文档](docs/DEVELOPMENT.md)

### 开发环境配置
```bash
# 克隆项目
git clone <repository-url>
cd file_server

# 安装依赖
uv sync

# 复制配置文件
cp config.yaml.example config.yaml

# 启动开发服务器
uv run uvicorn main:app --reload
```

## 贡献流程

### 1. 创建Issue
在开始开发之前，请先创建或查看相关的Issue:
- **Bug报告**: 使用Bug模板，详细描述问题
- **功能请求**: 使用功能请求模板，说明需求背景
- **改进建议**: 描述当前问题和改进方案

### 2. 分支管理
```bash
# 创建功能分支
git checkout -b feature/your-feature-name

# 创建修复分支
git checkout -b fix/issue-description

# 创建文档分支
git checkout -b docs/update-readme
```

### 3. 开发规范

#### 代码风格
- 遵循 PEP 8 Python编码规范
- 使用类型提示 (Type Hints)
- 编写清晰的文档字符串
- 保持函数简洁，单一职责

#### 示例代码
```python
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from app.models.responses import BaseResponse

router = APIRouter()

async def process_file(
    file_url: str,
    user_id: str,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """处理文件的业务逻辑
    
    Args:
        file_url: 文件URL
        user_id: 用户ID
        options: 可选配置参数
        
    Returns:
        处理结果字典
        
    Raises:
        HTTPException: 当文件处理失败时
    """
    try:
        # 业务逻辑实现
        result = {"status": "success"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 提交消息规范
使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范:

```bash
# 功能开发
git commit -m "feat: 添加文件批量上传功能"

# Bug修复
git commit -m "fix: 修复文件删除时的内存泄漏"

# 重构
git commit -m "refactor: 重构文件处理服务层"

# 文档更新
git commit -m "docs: 更新API接口文档"

# 测试相关
git commit -m "test: 添加文件上传单元测试"

# 构建相关
git commit -m "build: 更新依赖包版本"
```

### 4. 测试要求

#### 单元测试
```bash
# 运行所有测试
uv run pytest

# 运行特定模块测试
uv run pytest tests/test_file_service.py

# 查看测试覆盖率
uv run pytest --cov=app --cov-report=html
```

#### 测试编写示例
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """测试健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_file_upload():
    """测试文件上传"""
    with open("test_file.pdf", "rb") as f:
        response = client.post(
            "/upload_minio",
            files={"upload_file": f},
            data={"user_id": "test_user"}
        )
    assert response.status_code == 200
    assert "file_url" in response.json()["data"]
```

### 5. 代码审查

#### 审查清单
- [ ] 代码符合项目编码规范
- [ ] 添加了必要的测试用例
- [ ] 测试通过且覆盖率adequate
- [ ] 更新了相关文档
- [ ] 没有引入安全漏洞
- [ ] 性能影响可接受
- [ ] 向后兼容性良好

#### PR模板
```markdown
## 变更描述
简要描述此PR的更改内容

## 变更类型
- [ ] 新功能
- [ ] Bug修复
- [ ] 重构
- [ ] 文档更新
- [ ] 其他

## 测试
- [ ] 添加了单元测试
- [ ] 添加了集成测试
- [ ] 手动测试通过

## 影响范围
描述此变更可能影响的功能模块

## 截图/日志
如适用，提供相关截图或日志

## 检查项
- [ ] 代码符合规范
- [ ] 文档已更新
- [ ] 测试已通过
- [ ] 无breaking changes
```

## 项目结构说明

### 当前重构进展
```
file_server/
├── app/                    # 新架构 (重构中)
│   ├── core/              # 核心配置
│   ├── api/               # API层
│   ├── services/          # 业务逻辑
│   └── models/            # 数据模型
├── main.py                # 当前入口 (待重构)
├── utils/                 # 工具函数
├── src/                   # 旧代码 (待迁移)
└── docs/                  # 项目文档
```

### 重构任务
参与重构可以从以下任务开始:
1. **拆分路由**: 将main.py中的路由分离到app/api/v1/endpoints/
2. **服务层抽象**: 将业务逻辑移至app/services/
3. **配置统一**: 使用app/core/config.py统一配置管理
4. **错误处理**: 实现统一的异常处理机制
5. **测试补充**: 为新模块编写测试用例

## 发布流程

### 版本号规范
使用 [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- `1.0.0` → `1.0.1` (patch: Bug修复)
- `1.0.1` → `1.1.0` (minor: 新功能)
- `1.1.0` → `2.0.0` (major: 破坏性变更)

### 发布清单
- [ ] 更新版本号
- [ ] 更新CHANGELOG.md
- [ ] 确保所有测试通过
- [ ] 更新文档
- [ ] 创建Release标签
- [ ] 部署到测试环境验证

## 社区规范

### 行为准则
- 尊重所有贡献者
- 建设性地参与讨论
- 接受建设性的反馈
- 帮助新贡献者入门

### 沟通渠道
- **Issue**: 报告Bug和功能请求
- **Discussion**: 设计讨论和问答
- **PR**: 代码审查和技术讨论

## 获得帮助

如果您在贡献过程中遇到问题:
1. 查看[常见问题文档](docs/FAQ.md)
2. 搜索现有的Issues
3. 创建新的Issue寻求帮助
4. 参与GitHub Discussions

感谢您的贡献！🎉