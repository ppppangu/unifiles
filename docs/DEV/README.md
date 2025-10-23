# 开发文档 (DEV)

本目录包含 Unifiles 项目的开发相关文档。

## 📚 文档列表

### API 文档

#### `API_ENDPOINTS.md` ✅ 权威文档
完整的 API 端点参考文档，包含所有可用的 REST API 端点。

**内容包括**:
- 系统端点 (`/health`)
- 用户管理端点 (`/users`)
- 文件管理端点 (`/files`)
- 内容提取端点 (`/files/{file_id}/extract`)
- 知识库管理端点 (`/knowledge-bases`)
- 知识库检索端点 (`/knowledge-bases/{kb_id}/search`) 🆕
- 管理员端点 (`/manager`)

**使用场景**:
- 前端开发时查看 API 接口定义
- 编写客户端 SDK
- API 测试和集成

**更新策略**: 每次添加新端点或修改现有端点时必须更新此文档

---

#### `USER_ACCESS_KEY_API.md`
用户访问密钥管理 API 的详细文档。

**内容包括**:
- 访问密钥的创建、查询、删除
- 认证流程说明
- 权限管理

**使用场景**:
- 实现用户认证功能
- 理解访问控制机制

---

### 架构设计文档

#### `logging_system_design.md`
日志系统的设计文档。

**内容包括**:
- 日志级别和格式
- 日志输出配置
- 日志最佳实践

**使用场景**:
- 了解系统日志机制
- 添加新的日志记录点

---

## 🗑️ 已清理的文档

以下文档因与代码冲突或过时已被删除（2025-10-23）：

- ❌ `deprecated_database_usage_analysis.md` - 已过时的数据库使用分析
- ❌ `endpoint_extract_file_content_sequence.md` - 提取端点序列图（流程已变更）
- ❌ `FILE_UPLOAD_WORKFLOW_CN.md` - 文件上传工作流程（架构已更新）
- ❌ `测试端点/` 整个目录 - 临时测试文档和过时的 TODO 列表

**删除原因**:
- 描述的实现已被重构
- 引用了已废弃的类和模块（如 `DatabaseManager`）
- 测试结果包含过时的 API Key
- 内容与当前代码库不一致

---

## 📝 文档维护规范

### 何时更新文档

1. **添加新的 API 端点** → 更新 `API_ENDPOINTS.md`
2. **修改现有端点** → 更新 `API_ENDPOINTS.md`
3. **更改认证机制** → 更新 `USER_ACCESS_KEY_API.md`
4. **修改日志系统** → 更新 `logging_system_design.md`

### 文档质量标准

✅ **好的文档**:
- 与当前代码实现保持一致
- 包含完整的请求/响应示例
- 使用真实（或合理的示例）数据
- 定期更新

❌ **应该删除的文档**:
- 描述已废弃的功能
- 引用不存在的类/模块
- 包含过时的 API Key 或敏感信息
- 临时测试结果和 TODO 列表

### 文档组织原则

- **API 文档** → 放在 `docs/DEV/`
- **架构设计** → 放在 `docs/DEV/` 或 `docs/architecture/`
- **用户教程** → 放在 `docs/tutorials/`
- **临时笔记** → 不要提交到代码库

---

## 🔗 相关文档

- **项目总体文档**: `docs/README.md`
- **API 设计规范**: `docs/api_design_specification.md`
- **开发指南**: `CLAUDE.md`
- **项目结构**: `PROJECT_STRUCTURE.md`

---

**最后更新**: 2025-10-23
**维护者**: 开发团队
