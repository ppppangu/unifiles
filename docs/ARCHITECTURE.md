# 架构设计

本文档详细阐述了 Unifiles Core 的核心架构设计，旨在为开发者提供一个清晰、全面的系统认知。

## 1. 核心设计理念

### 以Markdown为核心

架构的核心思想是**以Markdown作为内容的单一真实来源（Single Source of Truth）**。所有不同格式的输入文件（如PDF, Word, 图片）都会被统一处理和转换为标准化的Markdown格式。

这种设计的优势在于：
- **内容统一性**: 消除多格式带来的不一致性，所有内容处理都基于统一的Markdown结构。
- **存储高效性**: Markdown是轻量级文本格式，易于存储、索引和版本控制。图片等二进制资源被独立存储并引用，避免冗余。
- **处理灵活性**: 同一份Markdown内容可以根据不同业务场景（如问答、分析、检索）应用不同的分块和索引策略，实现内容的一次提取、多次使用。

### 设计原则
- **高内聚，低耦合**: 各模块功能独立，通过清晰的接口交互。
- **可扩展性**: 采用策略模式，可以轻松添加新的文件格式支持、分块算法或嵌入模型。
- **状态清晰**: 对文档处理的每一步进行状态跟踪，确保流程的可追溯性和可恢复性。
- **异步优先**: 核心流程采用异步设计，以实现高性能和高并发。

## 2. 系统架构

系统采用分层架构，自上而下分为应用层、核心层和存储层。

### 2.1 架构分层图

```mermaid
graph TB
    subgraph "应用层 (Application Layer)"
        V1[V1 RESTful API<br/>端口8088]
    end
    
    subgraph "核心层 (Core Layer)"
        PIPE[Pipeline<br/>文档处理流水线]
        SVC[Services<br/>业务服务]
        DB_ABSTRACTION[Database<br/>数据库抽象]
    end
    
    subgraph "存储层 (Storage Layer)"
        MINIO[(MinIO<br/>对象存储)]
        PG[(PostgreSQL<br/>元数据 & 向量)]
    end
    
    V1 --> PIPE
    V1 --> SVC
    SVC --> DB_ABSTRACTION
    PIPE --> SVC
    SVC --> MINIO
    DB_ABSTRACTION --> PG
```

### 2.2 数据处理流程

从文件上传到知识库查询的完整数据流如下：
```mermaid
graph TD
    subgraph "第一步: 文件上传"
        direction LR
        A["用户上传文件<br/>(POST /files)"] --> S1{FileService};
        S1 --> |步骤1: 如需转换| CONV[格式转换为PDF];
        S1 --> |步骤2: 上传至对象存储| MINIO[(MinIO)];
        CONV --> MINIO;
        MINIO --> S1;
        S1 --> |步骤3: 写入数据库| F_TBL[files 表];
        S1 --> |步骤4: 记录日志| LOG_TBL[file_processing_logs 表];
    end

    subgraph "第二步: 内容提取"
        direction LR
        B["用户触发提取<br/>(POST /files/{file_id}/extract)"] --> S2{DocumentProcessingService};
        S2 --> |步骤1: 从files表获取路径| F_TBL;
        F_TBL --> S2;
        S2 --> |步骤2: 读取文件| MINIO;
        S2 --> |步骤3: OCR与内容处理| OCR[内容提取引擎];
        OCR --> |步骤4: 保存提取结果| ED_TBL["extracted_documents 表<br/>存储完整Markdown"];
        OCR --> |步骤5: 保存图片资源| EA_TBL[extracted_assets 表];
    end

    subgraph "第三步: 文档索引"
        direction LR
        C["用户创建知识库<br/>(POST /knowledge-bases)"] --> KB_TBL[knowledge_bases 表];
        D["用户索引文档<br/>(POST /kbs/{kb_id}/documents)"] --> S3{DocumentIndexingService};
        S3 --> |步骤1: 读取Markdown| ED_TBL;
        S3 --> |步骤2: 创建文档记录| DOC_TBL[documents 表];
        KB_TBL --> DOC_TBL;
        ED_TBL --> DOC_TBL;
        S3 --> |步骤3: 应用分块策略| CHUNK_SVC[分块服务];
        CHUNK_SVC --> |步骤4: 嵌入与存储| EMBED_SVC[嵌入服务];
        EMBED_SVC --> COMP_TBL["components 表<br/>(含向量)"];
        DOC_TBL --> COMP_TBL;
        COMP_TBL --> |子表| CHUNKS_TBL[chunks 表];
        COMP_TBL --> |子表| PHOTOS_TBL[photos 表];
    end

    subgraph "第四步: 知识库查询"
        direction LR
        E["用户查询<br/>(POST /kbs/{kb_id}/search)"] --> S4{SearchService};
        S4 --> |向量搜索| COMP_TBL;
        COMP_TBL --> S4;
        S4 --> F_OUT[返回相关Chunks];
    end
```

## 3. 文档处理流水线 (Pipeline)

文档处理是系统的核心，采用异步Pipeline模式，由一系列可插拔的处理阶段（Stage）串联而成。

```mermaid
graph TD
    A[输入文件] --> B{Validation};
    B --> C{Conversion};
    C --> D{OCR};
    D --> E{Chunking};
    E --> F{Embedding};
    F --> G{Storage};
    G --> H[处理完成];

    subgraph 监控与错误处理
        direction LR
        B --- S[Status Tracking];
        C --- S;
        D --- S;
        E --- S;
        F --- S;
        G --- S;
        S --- EH[Error Handling];
    end
```

### Pipeline核心组件
- **DocumentProcessor**: 主控制器，负责调度和执行所有处理阶段。
- **ProcessingContext**: 处理上下文，作为一个数据载体，在各个阶段之间传递文档信息、中间产物和状态。
- **ProcessingStage**: 处理阶段的抽象基类，定义了统一的 `process` 接口。每个具体阶段（如转换、OCR）都是它的实现。

### 主要处理阶段
1.  **Validation (验证)**: 检查文件格式、大小和完整性。
2.  **Conversion (格式转换)**: 将各种输入格式（Word, PPT, 图片等）统一转换为PDF格式，为OCR做准备。
3.  **OCR (内容提取)**: 使用OCR技术从PDF文件中提取文本和图片，生成标准化的Markdown内容。支持通过多模态大模型增强图片描述。
4.  **Chunking (分块)**: 根据配置的策略（如分层、语义）将Markdown内容和图片分割成小的逻辑单元（Chunks）。
5.  **Embedding (向量化)**: 使用指定的嵌入模型（如OpenAI, HuggingFace）将文本块和图片块转换为向量。
6.  **Storage (存储)**: 将分块内容、元数据和向量存储到PostgreSQL数据库中，以供后续检索。

## 4. 数据模型

系统的核心数据模型围绕文档处理流程设计，确保数据结构的清晰和一致。

### 关键实体说明
- **UserModel**: 系统用户。
- **AccessKeyModel**: 用户访问密钥。
- **FileModel**: 用户上传的原始文件记录。
- **ExtractedDocumentModel**: 从原始文件中提取的、标准化的Markdown内容。这是实现“一次提取，多次使用”的关键。
- **ExtractedAssetModel**: 从文档中提取的资源（如图片）。
- **KnowledgeBaseModel**: 用户创建的知识库，作为文档的组织单元。
- **DocumentModel**: 知识库中的一个文档条目，它引用一个`ExtractedContent`，并定义了该内容的特定处理方式（如分块策略）。
- **ComponentModel**: `Document`被分割后的最小单元的抽象，是检索的基本单位。
- **ChunkModel**: 文本类型的组件。
- **PhotoModel**: 图片类型的组件。

## 5. 数据库设计

数据库采用PostgreSQL，并利用 `pgvector` 扩展进行高效的向量存储和检索。

### 设计原则
- **零冗余**: `ExtractedDocumentModel` 表作为内容的唯一真实来源，避免了在不同知识库中重复存储相同内容。
- **高灵活性**: 同一个 `ExtractedDocumentModel` 可以被多个 `DocumentModel` 引用，每个 `DocumentModel` 可以采用不同的分块策略生成不同的 `ComponentModel` 集合，以适应不同场景。
- **关系清晰**: 表结构严格按照“文件 -> 提取内容 -> 知识库文档 -> 分块”的逻辑层次设计，关系清晰，易于维护。

通过这种设计，系统在保证数据一致性的同时，实现了极高的灵活性和存储效率。

## 6. web服务设计

### 整体架构图
```mermaid
graph TB
    subgraph "客户端层 (Client Layer)"
        WEB[Web界面]
        API_CLIENT[API客户端]
        MOBILE[移动端]
    end
    
    subgraph "API网关层 (API Gateway)"
        GATEWAY[FastAPI网关]
        AUTH[认证中间件]
        RATE_LIMIT[限流中间件]
    end
    
    subgraph "第一层: 文件管理服务"
        FILE_UPLOAD[文件上传]
        FILE_META[文件元数据]
        FILE_STORAGE[存储管理]
        FILE_ACCESS[访问控制]
    end
    
    subgraph "第二层: 文件处理服务"
        EXTRACT_QUEUE[提取任务队列]
        OCR_ENGINE[OCR引擎]
        CONTENT_PARSER[内容解析器]
        ASSET_PROCESSOR[资源处理器]
    end
    
    subgraph "第三层: 知识库服务"
        KB_MANAGER[知识库管理]
        DOC_INDEXER[文档索引器]
        VECTOR_SEARCH[向量搜索]
        CHUNK_PROCESSOR[分块处理器]
    end
    
    subgraph "存储层 (Storage Layer)"
        POSTGRES[(PostgreSQL + pgvector)]
        MINIO[(MinIO对象存储)]
        REDIS[(Redis缓存)]
    end
    
    WEB --> GATEWAY
    API_CLIENT --> GATEWAY
    MOBILE --> GATEWAY
    
    GATEWAY --> AUTH
    AUTH --> RATE_LIMIT
    
    RATE_LIMIT --> FILE_UPLOAD
    RATE_LIMIT --> FILE_META
    RATE_LIMIT --> KB_MANAGER
    
    FILE_UPLOAD --> FILE_STORAGE
    FILE_STORAGE --> MINIO
    FILE_META --> POSTGRES
    
    FILE_UPLOAD -.->|异步触发| EXTRACT_QUEUE
    EXTRACT_QUEUE --> OCR_ENGINE
    OCR_ENGINE --> CONTENT_PARSER
    CONTENT_PARSER --> ASSET_PROCESSOR
    ASSET_PROCESSOR --> POSTGRES
    ASSET_PROCESSOR --> MINIO
    
    CONTENT_PARSER -.->|自动索引| DOC_INDEXER
    DOC_INDEXER --> CHUNK_PROCESSOR
    CHUNK_PROCESSOR --> VECTOR_SEARCH
    VECTOR_SEARCH --> POSTGRES
    
    KB_MANAGER --> POSTGRES
    DOC_INDEXER --> POSTGRES
    
    EXTRACT_QUEUE --> REDIS
    VECTOR_SEARCH --> REDIS
```

## 7. 提供服务的业务分层
```
第一层: 文件上传和管理服务 (File Management Layer)
├── 文件上传、下载、删除
├── 文件元数据管理  
├── 存储空间管理
└── 访问权限控制

第二层: 文件处理服务 (File Processing Layer)
├── 文件格式验证和转换
├── OCR文本提取
├── 内容结构化处理
└── 处理状态管理

第三层: 知识库管理服务 (Knowledge Base Layer)
├── 知识库创建和管理
├── 文档索引和向量化
├── 知识检索和查询
└── 分块策略管理

第四层: 用户和系统管理服务 (User and System Management Layer)
├── 用户管理
├── 访问密钥管理
└── 系统状态监控
```

## 8. API Endpoints

### 架构原则
- **分层解耦**：每层职责明确，接口清晰
- **异步处理**：所有IO操作异步化
- **快速响应**：接口秒返回，后台异步处理
- **可扩展性**：支持水平扩展和微服务化

### 文件管理服务 (`unifiles.py`)

**职责**：
- 文件上传、下载、删除
- 文件元数据管理
- 存储空间管理
- 文件访问权限控制

**核心端点**：
- `POST /files` - 文件上传（秒返回）
- `GET /files` - 获取用户文件列表
- `GET /files/{file_id}` - 获取文件信息
- `DELETE /files/{file_id}` - 删除文件
- `GET /files/types` - 支持的文件类型

### 文件处理服务 (`processors.py`)

**职责**：
- 文件格式验证和转换
- OCR文本提取
- 内容结构化处理
- 处理状态管理

**核心端点**：
- `POST /files/{file_id}/extract` - 启动文件内容提取

### 知识库管理服务 (`knowledge_bases.py`)

**职责**：
- 知识库创建和管理
- 文档索引和向量化

**核心端点**：
- `GET /knowledge-bases` - 获取知识库列表
- `POST /knowledge-bases` - 创建知识库
- `POST /knowledge-bases/{kb_id}/documents` - 索引文档到知识库
- `GET /knowledge-bases/{kb_id}/documents` - 获取知识库文档
- `POST /knowledge-bases/{kb_id}/search` - 知识库搜索

### 用户管理服务 (`users.py`)

**职责**：
- 用户创建和管理
- 用户访问密钥管理

**核心端点**：
- `POST /users/create` - 创建新用户
- `GET /users/{user_id}` - 获取用户信息
- `POST /users/{user_id}/access-keys` - 创建用户访问密钥
- `GET /users/{user_id}/access-keys` - 获取用户访问密钥列表

### 系统管理服务 (`manager.py`)

**职责**：
- 系统状态监控

**核心端点**：
- `GET /manager/system/status` - 获取系统状态

## 9. Python 客户端

项目提供一个 Python 客户端 (`unifiles/client/client.py`)，用于与 Unifiles API 进行交互。该客户端封装了 API 请求的细节，提供了更便捷的编程接口。