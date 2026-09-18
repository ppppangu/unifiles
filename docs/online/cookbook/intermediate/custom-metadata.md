# 元数据与标签

元数据和标签是组织和检索文档的强大工具。本教程讲解如何利用它们实现精细化管理和过滤搜索。

## 元数据 vs 标签

```
元数据 (metadata)：键值对形式，支持复杂结构
├── 适合：结构化属性（部门、版本、日期）
├── 支持：过滤查询、范围查询
└── 示例：{"department": "HR", "version": "2.0"}

标签 (tags)：字符串数组
├── 适合：分类标记
├── 支持：简单过滤
└── 示例：["重要", "待审核", "2024"]
```

## 文件级元数据

### 上传时设置

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

file = client.files.upload(
    path="contract.pdf",
    metadata={
        "department": "法务部",
        "project": "合同管理系统",
        "contract_type": "服务合同",
        "party_a": "甲公司",
        "party_b": "乙公司",
        "sign_date": "2024-01-15",
        "expire_date": "2025-01-14",
        "value": 100000
    },
    tags=["合同", "重要", "2024"]
)
```

### 查询使用元数据

```python
# 按标签过滤
files = client.files.list(tags=["合同"])

# 按元数据过滤（如果API支持）
files = client.files.list(
    metadata_filter={"department": "法务部"}
)

# 获取文件时查看元数据
file = client.files.get(file_id)
print(file.metadata)
print(file.tags)
```

## 文档级元数据

在知识库中添加文档时可以设置额外元数据：

```python
# 创建知识库
kb = client.knowledge_bases.create(name="company-docs")

# 添加文档时设置元数据
doc = client.knowledge_bases.documents.create(
    kb_id=kb.id,
    file_id=file.id,
    title="采购合同模板 v2.0",
    metadata={
        "category": "模板",
        "sub_category": "采购类",
        "author": "法务部",
        "status": "已审核",
        "applicable_scope": "全公司",
        "revision": 2
    }
)
```

## 元数据过滤搜索

### 基本过滤

```python
# 只搜索特定类别的文档
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="付款条款",
    filter={
        "metadata.category": "合同"
    }
)
```

### 多条件过滤

```python
# 多个条件（AND）
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="审批流程",
    filter={
        "metadata.department": "HR",
        "metadata.status": "已发布"
    }
)
```

### 范围查询

```python
# 数值范围
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="合同条款",
    filter={
        "metadata.value": {"$gte": 100000}  # >= 10万
    }
)

# 日期范围
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="有效合同",
    filter={
        "metadata.expire_date": {"$gte": "2024-01-01"}
    }
)
```

### 列表包含

```python
# 部门在列表中
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="政策",
    filter={
        "metadata.department": {"$in": ["HR", "财务", "行政"]}
    }
)
```

## 过滤操作符

| 操作符 | 说明 | 示例 |
|-------|------|------|
| `$eq` | 等于（默认） | `{"field": "value"}` |
| `$ne` | 不等于 | `{"field": {"$ne": "value"}}` |
| `$gt` | 大于 | `{"field": {"$gt": 10}}` |
| `$gte` | 大于等于 | `{"field": {"$gte": 10}}` |
| `$lt` | 小于 | `{"field": {"$lt": 10}}` |
| `$lte` | 小于等于 | `{"field": {"$lte": 10}}` |
| `$in` | 在列表中 | `{"field": {"$in": ["a", "b"]}}` |
| `$nin` | 不在列表中 | `{"field": {"$nin": ["a", "b"]}}` |

## 实战示例

### 示例1：多租户文档管理

```python
# 上传时标记租户
def upload_tenant_document(tenant_id: str, file_path: str):
    return client.files.upload(
        path=file_path,
        metadata={
            "tenant_id": tenant_id,
            "uploaded_by": "system"
        }
    )

# 添加到知识库
def add_to_tenant_kb(kb_id: str, file_id: str, tenant_id: str):
    return client.knowledge_bases.documents.create(
        kb_id=kb_id,
        file_id=file_id,
        metadata={"tenant_id": tenant_id}
    )

# 搜索时限制租户
def search_tenant_docs(kb_id: str, tenant_id: str, query: str):
    return client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        filter={"metadata.tenant_id": tenant_id}
    )
```

### 示例2：文档版本管理

```python
# 上传新版本
def upload_new_version(doc_name: str, file_path: str, version: int):
    return client.files.upload(
        path=file_path,
        metadata={
            "doc_name": doc_name,
            "version": version,
            "is_latest": True,
            "uploaded_at": datetime.now().isoformat()
        }
    )

# 搜索最新版本
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="操作指南",
    filter={"metadata.is_latest": True}
)
```

### 示例3：按文档类型检索

```python
# 文档类型分类
DOCUMENT_TYPES = {
    "policy": "政策制度",
    "manual": "操作手册",
    "template": "模板文档",
    "report": "报告文档",
    "contract": "合同协议"
}

# 上传时分类
file = client.files.upload(
    path="hr_policy.pdf",
    metadata={
        "doc_type": "policy",
        "department": "HR"
    }
)

# 按类型搜索
def search_by_type(kb_id: str, doc_type: str, query: str):
    return client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        filter={"metadata.doc_type": doc_type}
    )

# 使用
results = search_by_type(kb.id, "policy", "年假规定")
```

### 示例4：权限控制

```python
# 文档权限级别
PERMISSION_LEVELS = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "secret": 3
}

# 上传时设置权限
file = client.files.upload(
    path="salary_report.xlsx",
    metadata={
        "permission_level": "confidential",
        "allowed_departments": ["HR", "财务"],
        "allowed_roles": ["manager", "hr_admin"]
    }
)

# 搜索时检查权限
def search_with_permission(kb_id: str, query: str, user_role: str, user_dept: str):
    # 确定用户可访问的权限级别
    accessible_levels = ["public", "internal"]
    if user_role in ["manager", "hr_admin"]:
        accessible_levels.append("confidential")
    
    return client.knowledge_bases.search(
        kb_id=kb_id,
        query=query,
        filter={
            "metadata.permission_level": {"$in": accessible_levels}
        }
    )
```

## 元数据设计最佳实践

### 1. 规划元数据架构

```python
# 定义元数据 Schema
DOCUMENT_METADATA_SCHEMA = {
    # 基础属性
    "doc_type": str,        # policy, manual, template, etc.
    "department": str,       # 所属部门
    "author": str,           # 作者
    
    # 状态属性
    "status": str,           # draft, review, published, archived
    "version": int,          # 版本号
    "is_latest": bool,       # 是否最新版
    
    # 时间属性
    "created_at": str,       # ISO 日期
    "updated_at": str,
    "effective_date": str,   # 生效日期
    "expire_date": str,      # 失效日期
    
    # 权限属性
    "permission_level": str,
    "allowed_roles": list,
    
    # 业务属性（可选）
    "project_id": str,
    "customer_id": str,
    "tags": list
}

def validate_metadata(metadata: dict) -> bool:
    """验证元数据是否符合 Schema"""
    required_fields = ["doc_type", "department", "status"]
    return all(field in metadata for field in required_fields)
```

### 2. 使用一致的命名

```python
# 好的命名
metadata = {
    "department": "HR",           # 清晰
    "created_at": "2024-01-15",   # ISO 格式
    "is_active": True             # 布尔值
}

# 避免的命名
metadata = {
    "dept": "HR",                  # 缩写不清晰
    "date": "15/01/2024",          # 格式不一致
    "active": "yes"                # 字符串代替布尔值
}
```

### 3. 避免过度嵌套

```python
# 推荐：扁平结构
metadata = {
    "author_name": "张三",
    "author_department": "HR",
    "author_email": "zhangsan@company.com"
}

# 避免：深度嵌套
metadata = {
    "author": {
        "info": {
            "name": "张三",
            "contact": {
                "email": "..."
            }
        }
    }
}
```

### 4. 预留扩展字段

```python
metadata = {
    # 核心字段
    "doc_type": "policy",
    "department": "HR",
    
    # 扩展字段
    "custom_fields": {
        "field1": "value1",
        "field2": "value2"
    }
}
```

## 标签使用建议

### 标签分类

```python
# 按类型组织标签
TAGS = {
    "status": ["待审核", "已发布", "已归档"],
    "priority": ["紧急", "重要", "普通"],
    "category": ["政策", "指南", "模板"],
    "year": ["2023", "2024", "2025"]
}

# 使用
file = client.files.upload(
    path="document.pdf",
    tags=["已发布", "重要", "政策", "2024"]
)
```

### 标签搜索

```python
# 按标签筛选文件
files = client.files.list(tags=["重要", "2024"])

# 搜索带特定标签的内容
results = client.knowledge_bases.search(
    kb_id=kb.id,
    query="审批流程",
    filter={"tags": {"$in": ["政策"]}}  # 如果支持
)
```

## 下一步

- [Webhook 集成](webhook-integration.md) - 元数据变更通知
- [多租户配置](../advanced/multi-tenant-setup.md) - 租户隔离方案
- [批量处理](batch-processing.md) - 批量设置元数据
