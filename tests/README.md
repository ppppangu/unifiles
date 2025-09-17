# Unifiles 测试文档

这个文档描述了为 unifiles.py 路由器创建的测试套件。

## 测试结构

```
tests/
├── README.md                           # 本文档
├── conftest.py                         # 测试配置和通用fixtures
├── test_config.py                      # 测试辅助配置和工具类
├── test_simple.py                      # 简单独立测试
├── run_tests.py                        # 测试运行脚本
├── unit/                               # 单元测试
│   ├── test_unifiles_router.py         # unifiles路由器核心功能单元测试
│   └── test_unifiles_edge_cases.py     # 边界情况和错误处理测试
└── integration/                        # 集成测试
    └── test_unifiles_integration.py    # unifiles路由器集成测试
```

## 测试覆盖

### 1. 核心功能测试 (`test_unifiles_router.py`)

测试 unifiles 路由器的所有主要端点：

- **文件类型支持**: 测试 `get_supported_file_types()` 端点
- **文件上传**: 测试 `upload_file()` 端点的各种场景
- **文件列表**: 测试 `list_user_files()` 端点和分页功能
- **文件信息**: 测试 `get_file_info()` 端点
- **公开状态更新**: 测试 `update_file_public_status()` 端点
- **文件删除**: 测试 `delete_file()` 端点

每个功能都包括：
- ✅ 成功场景测试
- ❌ 错误场景测试
- 🔒 权限验证测试
- 📊 边界条件测试

### 2. 边界情况测试 (`test_unifiles_edge_cases.py`)

测试各种边界情况和错误处理：

- **文件名处理**: 超长文件名、特殊字符、Unicode字符
- **内容类型**: 未知文件类型、空文件、大文件
- **并发场景**: 同名文件上传、竞态条件
- **安全测试**: 路径遍历攻击、SQL注入尝试、跨用户访问
- **性能测试**: 大量文件列表、内存效率

### 3. 集成测试 (`test_unifiles_integration.py`)

测试完整的请求-响应流程：

- **端到端场景**: 完整的文件生命周期测试
- **中间件集成**: 认证中间件的集成测试
- **错误处理**: HTTP错误响应的集成测试
- **性能场景**: 大文件和并发操作的集成测试

## 测试工具和配置

### Fixtures (`conftest.py`)

提供常用的测试 fixtures：

- `mock_user_id`, `mock_file_id`: 基础测试数据
- `mock_request`: 模拟 FastAPI 请求对象
- `sample_upload_file`: 测试文件上传对象
- `sample_file_records`: 模拟数据库记录
- `mock_storage_manager`: 存储管理器模拟
- `mock_file_db_manager`: 数据库管理器模拟

### 测试工具 (`test_config.py`)

提供测试辅助工具：

- `MockServices`: 模拟服务类工厂
- `TestDataFactory`: 测试数据生成器
- `TestAssertions`: 测试断言辅助函数
- `MockAuthMiddleware`: 认证中间件模拟

## 运行测试

### 运行所有测试
```bash
uv run python -m pytest tests/ -v
```

### 运行特定测试类别
```bash
# 只运行单元测试
uv run python -m pytest tests/unit/ -v

# 只运行集成测试
uv run python -m pytest tests/integration/ -v

# 运行特定测试文件
uv run python -m pytest tests/unit/test_unifiles_router.py -v
```

### 使用测试脚本
```bash
python tests/run_tests.py
```

### 运行简单验证测试
```bash
uv run python -m pytest tests/test_simple.py -v
```

## 测试状态

### ✅ 已完成的测试

1. **基础框架**: 测试配置和 fixtures 已建立
2. **单元测试**: 核心路由器功能的全面测试
3. **边界测试**: 错误处理和边界情况测试
4. **集成框架**: 集成测试结构已建立
5. **简单验证**: 独立验证测试可运行

### ⚠️ 当前限制

1. **导入路径**: 由于项目使用 `server` 作为根模块，部分导入需要调整
2. **认证集成**: 完整的认证中间件集成测试需要进一步配置
3. **实际数据库**: 当前使用模拟对象，实际数据库集成测试待完善

### 🔄 测试运行状态

- `test_simple.py`: ✅ 全部通过 (6/6)
- `test_unifiles_router.py`: ⚠️ 需要解决导入路径问题
- `test_unifiles_edge_cases.py`: ⚠️ 需要解决导入路径问题
- `test_unifiles_integration.py`: ⚠️ 需要解决导入路径和认证问题

## 最佳实践

### 测试编写原则

1. **独立性**: 每个测试应该独立运行，不依赖其他测试的状态
2. **可重复性**: 测试结果应该可重复和确定性
3. **清晰性**: 测试名称和断言应该清楚表达测试意图
4. **全面性**: 覆盖正常流程、错误情况和边界条件

### Mock 使用指南

1. **适度模拟**: 只模拟必要的外部依赖
2. **真实行为**: 模拟对象应该模拟真实对象的行为
3. **验证调用**: 验证重要的方法调用和参数
4. **清理状态**: 在测试后清理模拟状态

### 断言策略

1. **具体断言**: 使用具体的断言而不是泛泛的 True/False
2. **错误信息**: 提供有意义的错误信息
3. **多重验证**: 对复杂对象进行多个方面的验证
4. **异常测试**: 正确测试异常的类型和消息

## 后续改进

### 短期目标

1. **修复导入**: 解决模块导入路径问题
2. **完善集成**: 完成认证中间件的集成测试
3. **数据库测试**: 添加真实数据库的集成测试

### 长期目标

1. **覆盖率报告**: 添加测试覆盖率报告
2. **性能基准**: 建立性能测试基准
3. **自动化CI**: 集成到CI/CD流水线
4. **测试数据**: 建立更丰富的测试数据集

## 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [unittest.mock 文档](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI 测试指南](https://fastapi.tiangolo.com/tutorial/testing/)
- [Python 测试最佳实践](https://docs.python-guide.org/writing/tests/)