# Unifiles API 端点测试 TODO 列表

## 系统接口 (System)

### ✅ 已测试

- [x] `GET /health` - 系统健康检查
  - 测试状态: ✅ 已测试
  - 测试文件: 无单独测试文件
  - 备注: 基本健康检查端点，返回服务状态

### 🚧 未测试

- [ ] `GET /manager/system/status` - 获取系统状态信息（管理员专用）
  - 测试状态: ❌ 未测试
  - 备注: 需要管理员权限，返回系统组件状态

---

## 文件接口 (Files)

### ✅ 已测试

- [x] `POST /files` - 上传文件
  - 测试状态: ✅ 已测试
  - 测试文件: `test_file_upload_api.sh`
  - 测试结果: `file_upload_test_results.md`

- [x] `GET /files` - 获取用户文件列表
  - 测试状态: ✅ 已测试
  - 测试文件: `test_file_upload_api.sh`
  - 测试结果: `file_upload_test_results.md`

- [x] `GET /files/{file_id}` - 获取特定文件信息
  - 测试状态: ✅ 已测试
  - 测试文件: `test_file_upload_api.sh`
  - 测试结果: `file_upload_test_results.md`

- [x] `PATCH /files/{file_id}/public-status` - 更新文件公开状态
  - 测试状态: ✅ 已测试
  - 测试文件: `test_file_upload_api.sh`
  - 测试结果: `file_upload_test_results.md`

### 🚧 未测试

- [ ] `GET /files/types` - 获取支持的文件类型
  - 测试状态: ❌ 未测试
  - 备注: 返回系统支持的所有文件类型列表

- [ ] `DELETE /files/{file_id}` - 删除文件
  - 测试状态: ❌ 未测试
  - 备注: 删除指定文件及其相关数据

- [ ] `GET /files/public/{file_id}` - 获取公共文件信息（无需认证）
  - 测试状态: ❌ 未测试
  - 备注: 公开访问端点，无需认证

- [ ] `GET /files/admin/health` - 获取存储后端健康状态（管理员功能）
  - 测试状态: ❌ 未测试
  - 备注: 需要管理员权限

- [ ] `GET /files/admin/metrics` - 获取存储指标（管理员功能）
  - 测试状态: ❌ 未测试
  - 备注: 需要管理员权限

- [ ] `GET /files/user/stats` - 获取用户存储统计信息
  - 测试状态: ❌ 未测试
  - 备注: 返回用户存储使用情况统计

---

## 处理接口 (Processors)

### 🚧 未测试

- [ ] `POST /files/{file_id}/extract` - 提取文件内容
  - 测试状态: ❌ 未测试
  - 备注: 支持多种提取模式（simple, ocr提供商名称）
  - 实现状态: 🚧 开发中 (核心逻辑待实现)

---

## 知识库接口 (Knowledge Bases)

### 🚧 未测试

- [ ] `POST /knowledge-bases` - 创建新的知识库
  - 测试状态: ❌ 未测试
  - 实现状态: ✅ 已实现

- [ ] `GET /knowledge-bases` - 获取用户的知识库列表
  - 测试状态: ❌ 未测试
  - 备注: 当前返回模拟数据
  - 实现状态: 🚧 开发中 (返回示例数据)

- [ ] `GET /knowledge-bases/{kb_id}` - 获取知识库信息
  - 测试状态: ❌ 未测试
  - 实现状态: 🚧 开发中 (501 Not Implemented)

- [ ] `POST /knowledge-bases/{kb_id}/documents` - 将已提取的内容索引到知识库
  - 测试状态: ❌ 未测试
  - 备注: 当前返回模拟响应
  - 实现状态: 🚧 开发中 (501 Not Implemented)

- [ ] `GET /knowledge-bases/{kb_id}/documents` - 获取知识库文档列表
  - 测试状态: ❌ 未测试
  - 实现状态: 🚧 开发中 (501 Not Implemented)

- [ ] `DELETE /knowledge-bases/{kb_id}/documents/{doc_id}` - 删除知识库文档
  - 测试状态: ❌ 未测试
  - 实现状态: 🚧 开发中 (501 Not Implemented)

---

## 用户接口 (Users)

### 🚧 未测试

- [ ] `POST /users/create` - 创建新用户
  - 测试状态: ❌ 未测试
  - 备注: 不需要认证

- [ ] `GET /users/{user_id}` - 获取用户信息
  - 测试状态: ❌ 未测试
  - 备注: 不需要认证

- [ ] `POST /users/login` - 用户登录（通过邮箱获取用户信息）
  - 测试状态: ❌ 未测试
  - 备注: 不需要认证

- [ ] `POST /users/{user_id}/access-keys` - 为指定用户创建访问密钥（API Key）
  - 测试状态: ❌ 未测试
  - 备注: 调用数据库函数生成密钥

- [ ] `GET /users/{user_id}/access-keys` - 获取指定用户的访问密钥列表
  - 测试状态: ❌ 未测试
  - 备注: 可选按是否启用过滤

- [ ] `DELETE /users/{user_id}/access-keys/{key_id}` - 删除（撤销）指定用户的访问密钥
  - 测试状态: ❌ 未测试
  - 备注: 实际执行软删除，将密钥标记为不活跃状态

---

## 测试优先级建议

### 高优先级（核心功能）
1. `DELETE /files/{file_id}` - 文件删除是基本CRUD操作
2. `POST /files/{file_id}/extract` - 文件内容提取是知识库功能的前置步骤
3. `GET /files/types` - 获取支持的文件类型是客户端常用功能

### 中优先级（增强功能）
1. `POST /knowledge-bases` - 知识库创建
2. `GET /files/user/stats` - 用户存储统计
3. `GET /files/public/{file_id}` - 公开文件访问

### 低优先级（管理功能）
1. `POST /users/create` - 用户创建
2. `POST /users/{user_id}/access-keys` - API Key创建
3. `GET /manager/system/status` - 系统状态检查

---

## 测试脚本建议

建议创建以下测试脚本：
1. `test_file_management_api.sh` - 完整的文件管理API测试（包括删除）
2. `test_content_extraction_api.sh` - 文件内容提取API测试
3. `test_knowledge_base_api.sh` - 知识库API测试
4. `test_user_management_api.sh` - 用户管理API测试
5. `test_admin_api.sh` - 管理员API测试

---

## 更新日志

- 2025-10-14: 初始版本，基于代码审查创建TODO列表