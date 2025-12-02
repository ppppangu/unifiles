# 技术深潜

深入了解 Unifiles 的内部架构和实现细节。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│              Python SDK / REST API / LangChain                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API 网关层                                │
│         认证 → 限流 → 验证 → 路由 → 响应                         │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   文件服务      │ │   提取服务       │ │  知识库服务      │
│   (Layer 1)    │ │   (Layer 2)     │ │   (Layer 3)     │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        核心服务层                                │
│    FileService │ ExtractionService │ KnowledgeBaseService       │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │     Redis       │ │     MinIO       │
│   (pgvector)    │ │   (队列/缓存)    │ │   (对象存储)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 核心组件

### 应用层 (`unifiles/server/`)

| 组件 | 职责 |
|------|------|
| `main.py` | 应用入口，生命周期管理 |
| `routers/` | API 路由定义 |
| `middlewares.py` | 认证、限流、验证中间件 |
| `schemas/` | 请求/响应数据模型 |

### 核心层 (`unifiles/core/`)

| 组件 | 职责 |
|------|------|
| `services/` | 业务逻辑服务 |
| `pipelines/` | 文档处理管线 |
| `database/` | 数据库模型和连接管理 |
| `storage/` | 对象存储抽象 |
| `security/` | 加密和认证 |

### Worker 层 (`unifiles/workers/`)

| 组件 | 职责 |
|------|------|
| `upload_worker.py` | 处理文件上传任务 |
| `extraction_worker.py` | 处理内容提取任务 |
| `base_worker.py` | Worker 基类 |

## 数据流

### 文件上传流程

```
客户端 → API → FileService → MinIO (存储)
                    ↓
              PostgreSQL (元数据)
                    ↓
              Redis (上传队列)
                    ↓
           UploadWorker (后台处理)
```

### 内容提取流程

```
API → ExtractionService → Redis (提取队列)
                              ↓
                    ExtractionWorker
                              ↓
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    文件转换              OCR 识别            后处理
    (PDF等)             (图片/扫描件)        (结构化)
         └────────────────────┼────────────────────┘
                              ↓
                    Markdown 输出
                              ↓
                    PostgreSQL (存储)
```

### 知识库搜索流程

```
API → KnowledgeBaseService → 查询预处理
                                  ↓
                           嵌入生成 (OpenAI)
                                  ↓
                    PostgreSQL + pgvector (向量搜索)
                                  ↓
                           结果排序和过滤
                                  ↓
                           返回匹配分块
```

## 深入主题

<div class="grid cards" markdown>

-   :material-pipe:{ .lg .middle } **处理管线**

    ---

    从上传到索引的完整处理流程

    [:octicons-arrow-right-24: 处理管线](./processing-pipeline.md)

-   :material-database:{ .lg .middle } **数据库架构**

    ---

    PostgreSQL 表设计和 pgvector 配置

    [:octicons-arrow-right-24: 数据库架构](./database-schema.md)

-   :material-harddisk:{ .lg .middle } **存储架构**

    ---

    MinIO/S3 对象存储设计

    [:octicons-arrow-right-24: 存储架构](./storage-architecture.md)

-   :material-shield-lock:{ .lg .middle } **安全模型**

    ---

    认证、授权和数据加密

    [:octicons-arrow-right-24: 安全模型](./security-model.md)

-   :material-code-braces:{ .lg .middle } **开发技巧**

    ---

    本地开发环境搭建和调试

    [:octicons-arrow-right-24: 开发技巧](./development-tips.md)

</div>

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| API 框架 | FastAPI | 异步 Web 框架 |
| 数据库 | PostgreSQL 15+ | 关系数据存储 |
| 向量搜索 | pgvector | 向量索引和相似度搜索 |
| 缓存/队列 | Redis | 任务队列和缓存 |
| 对象存储 | MinIO / S3 | 文件存储 |
| 嵌入模型 | OpenAI / 自定义 | 文本向量化 |
| OCR | 内置 / 第三方 | 文档识别 |

## 设计原则

### 1. 三层解耦

每一层独立运作，可单独使用：
- Layer 1 只负责存储
- Layer 2 只负责提取
- Layer 3 只负责检索

### 2. Markdown 即真相

所有提取结果统一为 Markdown：
- 消除格式碎片化
- 简化下游处理
- 保持结构信息

### 3. 零冗余存储

相同内容只存储一次：
- 文件通过哈希去重
- 提取结果可被多个文档引用
- 分块策略与存储解耦

### 4. 异步优先

所有耗时操作异步执行：
- 文件处理通过队列
- 提取任务后台运行
- 支持 Webhook 通知
