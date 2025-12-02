# 贡献指南

感谢你对 Unifiles 的关注！我们欢迎任何形式的贡献。

## 快速开始

### 环境搭建

```bash
# 1. Fork 并克隆项目
git clone https://github.com/your-username/Unifiles.git
cd Unifiles

# 2. 安装依赖 (推荐使用 uv)
uv sync

# 3. 启动基础服务
docker-compose up -d postgres redis minio

# 4. 运行数据库迁移
for f in scripts/sql/*.sql; do
    psql -U postgres -d unifiles -f "$f"
done

# 5. 启动开发服务器
uv run uvicorn unifiles.server.main:app --reload --port 8088
```

## 贡献类型

### Bug 报告

- 使用 GitHub Issues 提交
- 提供详细的复现步骤
- 包含错误日志和环境信息
- 说明期望行为和实际行为

### 功能建议

- 说明使用场景和预期效果
- 考虑对现有功能的影响
- 如果可能，提供 API 设计草案

### 代码贡献

- 新功能开发
- Bug 修复
- 性能优化
- 测试覆盖

### 文档改进

- 修正错误
- 补充示例
- 改进描述

## 开发流程

### 1. 创建分支

```bash
# 功能分支
git checkout -b feat/your-feature-name

# 修复分支
git checkout -b fix/issue-description

# 文档分支
git checkout -b docs/update-description
```

### 2. 编写代码

#### 代码规范

```python
async def upload_file(
    file: UploadFile,
    user_id: str,
    metadata: dict | None = None
) -> File:
    """
    上传文件到存储系统。
    
    Args:
        file: 上传的文件对象
        user_id: 用户 ID
        metadata: 可选的元数据
        
    Returns:
        File: 创建的文件记录
        
    Raises:
        ValidationError: 文件验证失败
        StorageError: 存储操作失败
    """
    # 实现逻辑
    pass
```

#### 类型注解

所有公开 API 必须有类型注解：

```python
from typing import Optional

def process_documents(
    documents: list[dict],
    options: Optional[dict] = None
) -> list[ProcessedDocument]:
    pass
```

### 3. 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/unit/test_file_service.py

# 测试覆盖率
uv run pytest --cov=unifiles --cov-report=html
```

#### 测试示例

```python
import pytest
from unifiles.core.services import FileService

@pytest.mark.asyncio
async def test_upload_file_success(file_service: FileService):
    """测试文件上传成功场景"""
    result = await file_service.upload(
        filename="test.pdf",
        content=b"PDF content",
        user_id="user_123"
    )
    
    assert result.id is not None
    assert result.status == "uploaded"
```

### 4. 提交代码

#### 提交信息格式

```
类型(范围): 简短描述

详细说明（可选）

Closes #123
```

**类型**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具

**示例**:

```bash
git commit -m "feat(api): add batch file upload endpoint

- Support multiple files in single request
- Add size limit validation
- Update API documentation

Closes #45"
```

### 5. 创建 Pull Request

#### PR 描述模板

```markdown
## 变更说明
简述本次 PR 的主要变更内容

## 解决的问题
- Closes #123

## 测试计划
- [ ] 单元测试通过
- [ ] 集成测试通过

## 检查清单
- [ ] 代码遵循项目规范
- [ ] 添加了必要的测试
- [ ] 文档已更新
```

## 代码质量

### 格式化

```bash
uv run python scripts/dev/format.py
```

### 检查

```bash
# Lint
uv run python scripts/check/lint.py

# 类型检查
uv run python scripts/check/type_check.py

# 全部检查
uv run python scripts/check/validate_all.py
```

## 架构指南

### 添加新的 API 端点

1. 在 `unifiles/server/routers/` 添加路由
2. 在 `unifiles/server/schemas/` 定义请求/响应模型
3. 在 `unifiles/core/services/` 实现业务逻辑
4. 添加测试
5. 更新 API 文档

### 添加新的服务

```python
# unifiles/core/services/my_service.py
from unifiles.core.services.base import BaseService

class MyService(BaseService):
    async def _setup(self):
        # 初始化资源
        pass
    
    async def _teardown(self):
        # 清理资源
        pass
    
    async def do_something(self, param: str) -> Result:
        self.ensure_initialized()
        # 业务逻辑
        pass
```

### 数据库变更

1. 在 `scripts/sql/` 添加编号的迁移脚本
2. 更新 `unifiles/core/database/models.py`
3. 更新文档中的 schema 说明

## 文档

### 在线文档

文档源文件在 `docs/online/`，使用 MkDocs 构建：

```bash
# 本地预览
uv run mkdocs serve

# 构建
uv run mkdocs build
```

### 代码注释

公开 API 必须有 docstring：

```python
async def search(
    self,
    kb_id: str,
    query: str,
    top_k: int = 10
) -> SearchResult:
    """
    在知识库中搜索相关内容。
    
    Args:
        kb_id: 知识库 ID
        query: 搜索查询
        top_k: 返回结果数量
        
    Returns:
        SearchResult: 包含匹配的分块列表
    """
```

## 发布流程

### 版本号

遵循语义化版本：`主版本.次版本.修订号`

- 主版本：不兼容的 API 变更
- 次版本：向后兼容的功能新增
- 修订号：向后兼容的 Bug 修复

### 发布检查清单

- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新

## 获取帮助

- [GitHub Discussions](https://github.com/ppppangu/Unifiles/discussions) - 讨论和问答
- [GitHub Issues](https://github.com/ppppangu/Unifiles/issues) - Bug 报告

---

感谢你的贡献！
