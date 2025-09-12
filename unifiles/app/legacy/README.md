# Legacy 版本文件服务器

## 概述
这是重构后的 legacy 版本，保持了原有功能的完整性，确保现有业务不受影响。

## 目录结构
```
server/app/legacy/
├── main.py                    # 主服务入口
├── mineru_process.py          # MinGRU 处理模块
├── delete_file_module.py      # 文件删除模块
├── graph_module.py            # 图谱处理模块
├── singleton_embedding.py     # 嵌入向量单例模块
├── fix/                       # 修复相关代码
│   └── fix_pg.py             # PostgreSQL 修复
├── start_legacy_server.py     # 启动脚本
└── README.md                  # 本说明文档
```

## 启动方式

### 方式一：使用启动脚本（推荐）
```bash
# 从项目根目录运行
python server/app/legacy/start_legacy_server.py
```

### 方式二：使用 uvicorn 直接启动
```bash
# 从项目根目录运行
uv run uvicorn server.app.legacy.main:app --http httptools --host 0.0.0.0 --port 8087 --log-level debug --access-log
```

## 主要变更

1. **目录迁移**: 将原有代码迁移到 `server/app/legacy/` 目录
2. **导入路径修复**: 修复了所有相对导入和配置文件路径
3. **模块化**: 使用相对导入确保模块间依赖正确
4. **配置路径**: 统一使用项目根目录的 `config.yaml`

## 功能说明

服务器提供以下主要功能：
1. 文件上传和存储（支持用户空间和公共空间）
2. 文件处理（OCR、向量化存储、图谱处理）
3. 文件删除和管理
4. 数据库修复和维护

## 测试验证

启动成功后，服务器将在 http://0.0.0.0:8087 上运行，日志显示：
```
INFO:     Uvicorn running on http://0.0.0.0:8087
Graph module initialized
Unifiles server started successfully
数据库修复检查完成
```

## 注意事项

- 确保项目根目录存在 `config.yaml` 配置文件
- 确保相关依赖（数据库、MinIO 等）服务正常运行
- 日志文件将保存在 `logs/` 目录下