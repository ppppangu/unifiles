# 开发文档

## 项目概述

文件服务器项目，提供文件上传、处理、删除和知识图谱生成等功能。

## 技术栈

- **框架**: FastAPI
- **Python**: >=3.11
- **包管理**: uv
- **数据库**: PostgreSQL + pgvector
- **对象存储**: MinIO
- **日志**: loguru

## 环境配置

### 1. 环境要求
```bash
# Python 3.11+
# uv (包管理器)
# PostgreSQL with pgvector
# MinIO
```

### 2. 安装依赖
```bash
uv sync
```

### 3. 配置文件
复制 `config.yaml.example` 到 `config.yaml` 并配置：

```yaml
server_components:
  minio:
    endpoint: "localhost:9000"
    access_key: "your_access_key"
    secret_key: "your_secret_key"
    bucket: "file-server"
    public_url_prefix: "http://localhost:9000"
  
  pg_vector:
    host: "localhost"
    port: 5432
    database: "file_server"
    user: "postgres"
    password: "your_password"
```

### 4. 启动服务
```bash
# 开发环境
uv run uvicorn main:app --host 0.0.0.0 --port 8087 --reload

# 或者使用项目脚本
uv run python main.py
```

## 项目结构

```
file_server/
├── app/                    # 重构后的应用代码
│   ├── core/              # 核心配置
│   │   └── config.py      # 配置管理
│   ├── api/               # API层
│   │   └── v1/            # API v1版本
│   │       └── endpoints/ # 端点实现
│   ├── services/          # 业务逻辑层
│   ├── models/            # 数据模型
│   │   ├── requests.py    # 请求模型
│   │   └── responses.py   # 响应模型
│   └── utils/             # 工具函数
├── docs/                  # 项目文档
├── tests/                 # 测试代码
├── main.py                # 应用入口（待重构）
├── config.yaml            # 配置文件
└── pyproject.toml         # 项目配置
```

## API 接口

### 健康检查
- `GET /health` - 服务健康检查
- `GET /supported-file-types` - 获取支持的文件类型

### 文件操作
- `POST /upload_minio` - 文件上传
- `POST /process` - 文件处理
- `POST /delete_file` - 文件删除

### 知识图谱
- `POST /graph/knowledge_base` - 图谱生成和查询

## 开发规范

### 1. 代码规范
- 使用 Python 类型提示
- 遵循 PEP 8 代码风格
- 函数和类需要添加文档字符串

### 2. 提交规范
```bash
# 功能开发
git commit -m "feat: 添加文件上传功能"

# Bug修复
git commit -m "fix: 修复文件删除错误"

# 重构
git commit -m "refactor: 重构API路由结构"

# 文档
git commit -m "docs: 更新开发文档"
```

### 3. 分支策略
- `main`: 主分支，稳定版本
- `dev`: 开发分支，功能集成
- `feature/*`: 功能分支
- `fix/*`: 修复分支

## 部署

### Docker部署
```bash
# 构建镜像
docker build -t file-server .

# 运行容器
docker run -p 8087:8087 file-server
```

### 生产环境
```bash
# 使用gunicorn
uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8087
```

## 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_api.py

# 测试覆盖率
uv run pytest --cov=app
```

## 故障排查

### 常见问题
1. **MinIO连接失败**: 检查配置文件中的endpoint和认证信息
2. **数据库连接失败**: 确认PostgreSQL服务运行并安装了pgvector扩展
3. **文件上传失败**: 检查MinIO bucket权限和网络连接

### 日志查看
```bash
# 应用日志
tail -f logs/$(date +%Y-%m-%d).log

# 系统日志
journalctl -u file-server -f
```

## 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -m 'feat: 新功能描述'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建 Pull Request

## 许可证

[指定许可证类型]