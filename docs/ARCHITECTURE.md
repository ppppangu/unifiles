# 架构设计文档

## 系统概述

文件服务器是一个基于FastAPI的微服务，提供文件上传、处理、存储和知识图谱生成功能。

## 架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │    │   Web Frontend  │    │   Mobile Apps   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │      Load Balancer       │
                    └─────────────┬─────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │     FastAPI Server       │
                    │   (File Server API)      │
                    └─────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                       │                        │
┌───────┴──────┐    ┌───────────┴────────────┐    ┌──────┴───────┐
│    MinIO     │    │     PostgreSQL         │    │   External   │
│  (文件存储)   │    │   (向量数据库)          │    │   Services   │
└──────────────┘    └────────────────────────┘    └──────────────┘
```

## 模块架构

### 1. API层 (app/api)
```
app/api/
├── v1/
│   ├── endpoints/
│   │   ├── health.py      # 健康检查
│   │   ├── files.py       # 文件操作
│   │   └── graph.py       # 图谱操作
│   └── api.py             # 路由汇总
└── deps.py                # API依赖
```

**职责**:
- HTTP请求处理
- 参数验证
- 响应格式化
- 错误处理

### 2. 服务层 (app/services)
```
app/services/
├── file_service.py        # 文件服务
├── graph_service.py       # 图谱服务
├── storage_service.py     # 存储服务
└── processing_service.py  # 处理服务
```

**职责**:
- 业务逻辑实现
- 数据处理
- 外部服务调用
- 事务管理

### 3. 核心层 (app/core)
```
app/core/
├── config.py              # 配置管理
├── deps.py               # 依赖注入
├── database.py           # 数据库连接
└── exceptions.py         # 异常定义
```

**职责**:
- 配置管理
- 依赖注入
- 数据库连接池
- 全局异常处理

### 4. 模型层 (app/models)
```
app/models/
├── requests.py           # 请求模型
├── responses.py          # 响应模型
└── database.py           # 数据库模型
```

**职责**:
- 数据验证
- 类型定义
- 序列化/反序列化

## 数据流

### 文件上传流程
```
1. Client → API: 上传文件请求
2. API → Service: 参数验证，调用文件服务
3. Service → MinIO: 存储文件
4. Service → Database: 记录文件元信息
5. Service → API: 返回文件信息
6. API → Client: 响应上传结果
```

### 文件处理流程
```
1. Client → API: 文件处理请求
2. API → Service: 调用处理服务
3. Service → External: 调用转换服务(如格式转换)
4. Service → External: 调用OCR服务(MinERU)
5. Service → Database: 存储向量数据
6. Service → MinIO: 存储处理结果
7. Service → API: 返回处理结果
8. API → Client: 响应处理结果
```

## 存储设计

### MinIO对象存储
```
bucket/
├── users/
│   └── {user_id}/
│       └── {file_uuid}/
│           ├── original.{ext}     # 原文件
│           ├── converted.pdf      # 转换后PDF
│           └── processed.md       # 处理结果
└── public/
    └── shared_files/
```

### PostgreSQL数据库
```sql
-- 用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 知识库表
CREATE TABLE knowledge_bases (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    name TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 文档表
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    knowledge_base_id TEXT,
    file_url TEXT,
    file_name TEXT,
    file_type TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量表
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    chunk_text TEXT,
    embedding VECTOR(1536),
    metadata JSONB
);
```

## 外部服务

### 1. 格式转换服务
- **功能**: 文档格式转换 (docx→pdf, pptx→pdf等)
- **接口**: HTTP REST API
- **超时**: 60秒

### 2. OCR服务 (MinERU)
- **功能**: PDF文档解析和OCR识别
- **接口**: HTTP REST API
- **返回**: Markdown格式文本

### 3. 向量化服务
- **功能**: 文本向量化
- **模型**: text-embedding-ada-002 或自部署模型

## 配置管理

### 配置文件结构
```yaml
server:
  host: "0.0.0.0"
  port: 8087

server_components:
  minio:
    endpoint: "localhost:9000"
    access_key: "admin"
    secret_key: "password"
    bucket: "file-server"
    public_url_prefix: "http://localhost:9000"
  
  pg_vector:
    host: "localhost"
    port: 5432
    database: "file_server"
    user: "postgres"
    password: "password"
  
  convert_format_server:
    - url: "http://localhost:8088"
  
  mineru_server:
    - url: "http://localhost:8089"
```

## 部署架构

### 开发环境
```
┌─────────────────┐
│   Development   │
│     Server      │
│                 │
│ ┌─────────────┐ │
│ │ FastAPI App │ │
│ │   (uvicorn) │ │
│ └─────────────┘ │
│                 │
│ ┌─────────────┐ │
│ │   MinIO     │ │
│ └─────────────┘ │
│                 │
│ ┌─────────────┐ │
│ │ PostgreSQL  │ │
│ └─────────────┘ │
└─────────────────┘
```

### 生产环境
```
┌─────────────────┐    ┌─────────────────┐
│  Load Balancer  │────│      CDN        │
└─────────┬───────┘    └─────────────────┘
          │
    ┌─────┴─────┐
    │   API     │
    │ Cluster   │
    │           │
    │ ┌───────┐ │
    │ │FastAPI│ │
    │ │   x3  │ │
    │ └───────┘ │
    └─────┬─────┘
          │
┌─────────┼─────────┐
│         │         │
│ ┌───────┴──────┐  │  ┌─────────────┐
│ │   MinIO      │  │  │ PostgreSQL  │
│ │   Cluster    │  │  │   Cluster   │
│ └──────────────┘  │  └─────────────┘
└───────────────────┘
```

## 安全考虑

### 1. 认证授权
- API密钥认证
- 用户权限控制
- 文件访问权限

### 2. 数据安全
- 文件存储加密
- 传输层安全(HTTPS)
- 数据库连接加密

### 3. 输入验证
- 文件类型限制
- 文件大小限制
- 参数格式验证

## 监控告警

### 1. 应用监控
- API响应时间
- 错误率统计
- 服务可用性

### 2. 基础设施监控
- CPU/内存使用率
- 磁盘空间
- 网络流量

### 3. 业务监控
- 文件上传成功率
- 处理任务队列长度
- 存储空间使用情况