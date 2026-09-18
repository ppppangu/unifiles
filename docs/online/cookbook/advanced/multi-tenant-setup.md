# 多租户配置

本教程讲解如何为 SaaS 应用构建多租户文档管理系统，实现数据隔离和权限控制。

## 多租户架构概述

```
                    ┌─────────────────────────────────┐
                    │         你的 SaaS 应用          │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │  租户 A   │  │  租户 B   │  │  租户 C   │
              │  Tenant A │  │  Tenant B │  │  Tenant C │
              └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │          Unifiles API         │
                    │    (通过元数据实现租户隔离)     │
                    └───────────────────────────────┘
```

## 隔离策略

### 策略1：元数据隔离（推荐）

使用元数据标记租户，所有资源共享同一个 Unifiles 账户：

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

class TenantIsolatedClient:
    """租户隔离的 Unifiles 客户端"""
    
    def __init__(self, client: UnifilesClient, tenant_id: str):
        self.client = client
        self.tenant_id = tenant_id
    
    def upload_file(self, path: str, **kwargs):
        """上传文件，自动添加租户标记"""
        metadata = kwargs.pop("metadata", {})
        metadata["tenant_id"] = self.tenant_id
        
        return self.client.files.upload(
            path=path,
            metadata=metadata,
            **kwargs
        )
    
    def list_files(self, **kwargs):
        """列出租户的文件"""
        page = self.client.files.list(**kwargs)
        return [
            file for file in page.items
            if file.metadata.get("tenant_id") == self.tenant_id
        ]
    
    def search_kb(self, kb_id: str, query: str, **kwargs):
        """搜索时限制租户范围"""
        filter_dict = kwargs.pop("filter", {})
        filter_dict["metadata.tenant_id"] = self.tenant_id
        
        return self.client.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            filter=filter_dict,
            **kwargs
        )

# 使用
tenant_a_client = TenantIsolatedClient(client, "tenant_a")
tenant_b_client = TenantIsolatedClient(client, "tenant_b")

# 租户 A 上传
file_a = tenant_a_client.upload_file("doc.pdf")

# 租户 A 搜索（只能搜到自己的文档）
results = tenant_a_client.search_kb("kb_shared", "查询内容")
```

### 策略2：知识库隔离

每个租户使用独立的知识库：

```python
class KnowledgeBaseIsolatedClient:
    """基于知识库的租户隔离"""
    
    def __init__(self, client: UnifilesClient, tenant_id: str):
        self.client = client
        self.tenant_id = tenant_id
        self._kb_cache = {}
    
    def get_tenant_kb(self, kb_name: str) -> str:
        """获取或创建租户专属知识库"""
        cache_key = f"{self.tenant_id}:{kb_name}"
        
        if cache_key not in self._kb_cache:
            # 查找或创建知识库
            full_name = f"{self.tenant_id}_{kb_name}"
            
            kbs = self.client.knowledge_bases.list()
            existing = next(
                (kb for kb in kbs.items if kb.name == full_name),
                None
            )
            
            if existing:
                self._kb_cache[cache_key] = existing.id
            else:
                kb = self.client.knowledge_bases.create(
                    name=full_name,
                    metadata={"tenant_id": self.tenant_id}
                )
                self._kb_cache[cache_key] = kb.id
        
        return self._kb_cache[cache_key]
    
    def add_document(self, kb_name: str, file_id: str, **kwargs):
        """添加文档到租户知识库"""
        kb_id = self.get_tenant_kb(kb_name)
        
        metadata = kwargs.pop("metadata", {})
        metadata["tenant_id"] = self.tenant_id
        
        return self.client.knowledge_bases.documents.create(
            kb_id=kb_id,
            file_id=file_id,
            metadata=metadata,
            **kwargs
        )
    
    def search(self, kb_name: str, query: str, **kwargs):
        """搜索租户知识库"""
        kb_id = self.get_tenant_kb(kb_name)
        return self.client.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            **kwargs
        )

# 使用
tenant_a = KnowledgeBaseIsolatedClient(client, "tenant_a")
tenant_b = KnowledgeBaseIsolatedClient(client, "tenant_b")

# 各自使用独立的知识库
tenant_a.add_document("main", file_id)
results_a = tenant_a.search("main", "查询")

tenant_b.add_document("main", file_id)
results_b = tenant_b.search("main", "查询")

# 实际知识库名：tenant_a_main, tenant_b_main
```

### 策略3：API Key 隔离

为每个租户创建独立的 API Key：

```python
class ApiKeyIsolatedClient:
    """基于 API Key 的租户隔离"""
    
    def __init__(self, master_client: UnifilesClient):
        self.master_client = master_client
        self._tenant_clients = {}
    
    def get_tenant_client(self, tenant_id: str) -> UnifilesClient:
        """获取租户专属客户端"""
        if tenant_id not in self._tenant_clients:
            # 创建或获取租户 API Key
            api_key = self._get_or_create_tenant_key(tenant_id)
            self._tenant_clients[tenant_id] = UnifilesClient(api_key=api_key)
        
        return self._tenant_clients[tenant_id]
    
    def _get_or_create_tenant_key(self, tenant_id: str) -> str:
        """获取或创建租户 API Key"""
        # 从数据库获取已有 Key
        existing_key = db.get_tenant_api_key(tenant_id)
        if existing_key:
            return existing_key
        
        # 创建新 Key
        key = self.master_client.api_keys.create(
            name=f"tenant_{tenant_id}",
            scopes=["files:*", "kb:*"],
            metadata={"tenant_id": tenant_id}
        )
        
        # 保存到数据库
        db.save_tenant_api_key(tenant_id, key.key)
        
        return key.key

# 使用
manager = ApiKeyIsolatedClient(master_client)

# 获取租户客户端
client_a = manager.get_tenant_client("tenant_a")
client_b = manager.get_tenant_client("tenant_b")

# 完全隔离的操作
file_a = client_a.files.upload("doc.pdf")
file_b = client_b.files.upload("doc.pdf")
```

## 完整多租户实现

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from unifiles import UnifilesClient

@dataclass
class Tenant:
    id: str
    name: str
    plan: str  # free, professional, enterprise
    config: Dict[str, Any]

class MultiTenantUnifilesService:
    """多租户 Unifiles 服务"""
    
    def __init__(self, api_key: str):
        self.client = UnifilesClient(api_key=api_key)
        self._tenant_kbs: Dict[str, str] = {}
    
    def get_kb_id(self, tenant: Tenant) -> str:
        """获取租户的知识库ID"""
        if tenant.id not in self._tenant_kbs:
            kb = self._create_tenant_kb(tenant)
            self._tenant_kbs[tenant.id] = kb.id
        return self._tenant_kbs[tenant.id]
    
    def _create_tenant_kb(self, tenant: Tenant):
        """为租户创建知识库"""
        # 根据套餐配置分块策略
        chunk_size = {
            "free": 256,
            "professional": 512,
            "enterprise": 1024
        }.get(tenant.plan, 512)
        
        return self.client.knowledge_bases.create(
            name=f"kb_{tenant.id}",
            description=f"Knowledge base for {tenant.name}",
            chunking_strategy={
                "type": "semantic",
                "chunk_size": chunk_size,
                "overlap": chunk_size // 10
            },
            metadata={"tenant_id": tenant.id, "plan": tenant.plan}
        )
    
    def upload_document(
        self,
        tenant: Tenant,
        file_path: str,
        metadata: Optional[Dict] = None
    ):
        """上传文档"""
        # 检查配额
        self._check_quota(tenant)
        
        # 上传文件
        file_metadata = metadata or {}
        file_metadata["tenant_id"] = tenant.id
        
        file = self.client.files.upload(
            path=file_path,
            metadata=file_metadata
        )
        
        # 提取内容
        extraction = self.client.extractions.create(file_id=file.id)
        extraction.wait()
        
        # 添加到知识库
        kb_id = self.get_kb_id(tenant)
        doc = self.client.knowledge_bases.documents.create(
            kb_id=kb_id,
            file_id=file.id,
            metadata=file_metadata
        )
        doc.wait()
        
        return {
            "file_id": file.id,
            "doc_id": doc.id,
            "chunks": doc.chunk_count
        }
    
    def search(
        self,
        tenant: Tenant,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ):
        """搜索租户文档"""
        kb_id = self.get_kb_id(tenant)
        
        # 强制添加租户过滤
        filter_dict = filters or {}
        filter_dict["metadata.tenant_id"] = tenant.id
        
        return self.client.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
            filter=filter_dict
        )
    
    def _check_quota(self, tenant: Tenant):
        """检查租户配额"""
        limits = {
            "free": {"files": 100, "storage_mb": 1024},
            "professional": {"files": 10000, "storage_mb": 102400},
            "enterprise": {"files": float("inf"), "storage_mb": float("inf")}
        }
        
        limit = limits.get(tenant.plan, limits["free"])
        
        # 获取当前使用量
        usage = self._get_tenant_usage(tenant)
        
        if usage["files"] >= limit["files"]:
            raise QuotaExceededError("文件数量已达上限")
        if usage["storage_mb"] >= limit["storage_mb"]:
            raise QuotaExceededError("存储空间已达上限")
    
    def _get_tenant_usage(self, tenant: Tenant) -> Dict:
        """获取租户使用量"""
        files = self.client.files.list(
            metadata_filter={"tenant_id": tenant.id}
        )
        
        total_size = sum(f.size for f in files.items)
        
        return {
            "files": files.total,
            "storage_mb": total_size / (1024 * 1024)
        }

# 使用示例
service = MultiTenantUnifilesService(api_key="<api-key>")

# 创建租户
tenant_a = Tenant(
    id="tenant_001",
    name="公司A",
    plan="professional",
    config={}
)

# 上传文档
result = service.upload_document(
    tenant=tenant_a,
    file_path="contract.pdf",
    metadata={"category": "合同"}
)

# 搜索
results = service.search(
    tenant=tenant_a,
    query="违约条款"
)
```

## Webhook 多租户处理

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
service = MultiTenantUnifilesService(api_key="<api-key>")

@app.route("/webhook/unifiles", methods=["POST"])
def webhook():
    event = request.json
    
    # 从元数据获取租户ID
    tenant_id = event["data"].get("metadata", {}).get("tenant_id")
    
    if not tenant_id:
        return jsonify({"error": "Missing tenant_id"}), 400
    
    # 获取租户信息
    tenant = db.get_tenant(tenant_id)
    
    if event["type"] == "extraction.completed":
        handle_extraction_completed(tenant, event["data"])
    elif event["type"] == "document.indexed":
        handle_document_indexed(tenant, event["data"])
    
    return jsonify({"ok": True})

def handle_extraction_completed(tenant: Tenant, data: dict):
    """处理提取完成事件"""
    # 通知租户的业务系统
    notify_tenant_system(tenant, "extraction_completed", data)

def handle_document_indexed(tenant: Tenant, data: dict):
    """处理索引完成事件"""
    # 更新租户的文档状态
    update_tenant_document_status(tenant, data["document_id"], "indexed")
```

## 数据迁移

### 租户间迁移

```python
def migrate_tenant_data(
    service: MultiTenantUnifilesService,
    source_tenant: Tenant,
    target_tenant: Tenant
):
    """将源租户的数据迁移到目标租户"""
    
    # 获取源租户的所有文件
    source_files = service.client.files.list(
        metadata_filter={"tenant_id": source_tenant.id}
    )
    
    migrated = []
    for file in source_files.items:
        # 下载文件
        content = service.client.files.download(file.id)
        
        # 以目标租户身份上传
        new_file = service.upload_document(
            tenant=target_tenant,
            file_content=content,
            metadata=file.metadata
        )
        
        migrated.append({
            "old_id": file.id,
            "new_id": new_file["file_id"]
        })
    
    return migrated
```

## 最佳实践

1. **始终验证租户上下文** - 每个请求都必须验证租户ID
2. **使用元数据双重保护** - 即使有知识库隔离，也添加元数据标记
3. **实现配额管理** - 按租户套餐限制资源使用
4. **审计日志** - 记录所有跨租户操作

## 下一步

- [性能调优](performance-tuning.md) - 多租户环境优化
- [元数据与标签](../intermediate/custom-metadata.md) - 元数据设计
- [Webhook 集成](../intermediate/webhook-integration.md) - 事件处理
