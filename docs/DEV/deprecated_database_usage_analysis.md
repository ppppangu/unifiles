# 调研：deprecated 数据库模块在 FastAPI 端点中的引用情况

本文档记录了对 `unifiles/core/database/deprecated/` 下弃用实现的引用调研，重点排查 FastAPI 端点是否仍直接或间接使用这些弃用路径。

## 结论

- 当前 FastAPI 端点代码未直接引用 `unifiles/core/database/deprecated` 下的类或函数。
- 服务层 `StorageService`（用于处理 PDF 存储与向量入库）通过 `DatabaseManager` 别名间接指向了弃用实现，但现有端点未调用到会触发该路径的方法，因此运行时不会触达弃用代码。

## 证据与定位

- 弃用实现位置：
  - `unifiles/core/database/deprecated/base.py`
  - `unifiles/core/database/deprecated/manager.py`
  - `unifiles/core/database/deprecated/secure_manager.py`

- 统一导出与弃用映射（别名）：
  - `unifiles/core/database/__init__.py:50` 将 `DatabaseManager` 指向弃用实现 `LegacyFullDatabaseManager`：
    - `unifiles/core/database/__init__.py:50`

- 服务层对 `DatabaseManager` 的使用（因此命中上面的弃用别名）：
  - 引入与实例化：
    - `unifiles/core/services/storage_service.py:14`
    - `unifiles/core/services/storage_service.py:24`
    - `unifiles/core/services/storage_service.py:148`

- FastAPI 端点实际使用（均未使用弃用实现）：
  - 用户端点使用统一管理器：
    - `unifiles/app/routers/users.py:24` `from unifiles.core.database import unified_db_manager`
  - 文件端点使用统一文件管理器别名（已指向新实现）：
    - `unifiles/app/routers/unifiles.py:23` `from unifiles.core.database import secure_file_db_manager`
      - 注意：`secure_file_db_manager` 在 `database/__init__.py` 中映射到新的统一实现，不是弃用实现。
  - 知识库端点使用统一管理器：
    - `unifiles/app/routers/knowledge_bases.py:29-33` 引入 `UnifiedKnowledgeBaseDBManager`、`unified_kb_db_manager`、`unified_user_db_manager`
    - `unifiles/app/routers/knowledge_bases.py:82` 调用 `await unified_user_db_manager.ensure_user_exists(user_id)`
  - 文件处理端点：
    - `unifiles/app/routers/processors.py:16-17` 引入 `secure_file_db_manager` 和 `get_document_processor`
    - 实际调用 `DocumentProcessingService.process_file_by_id`，不触发 `StorageService` 的 `DatabaseManager` 路径（该方法直接通过 `secure_file_db_manager` 获取文件记录并走 OCR/解析流程）。

## 影响与建议

- 影响：尽管理论上存在通过 `DatabaseManager` 的弃用指向，但当前端点未走到该路径，运行时不受影响。
- 建议（可选、去除“隐式”弃用依赖）：
  - 将 `unifiles/core/database/__init__.py:50` 的 `DatabaseManager` 别名改为指向新统一实现（例如 `UnifiedDatabaseManager`）。
  - 将 `unifiles/core/services/storage_service.py` 内对 `DatabaseManager` 的使用替换为统一管理器（如按职责拆分使用 `UnifiedKnowledgeBaseDBManager`、`UnifiedUserDBManager` 或 `unified_db_manager`）。

## 附注

- 文档中仍存在示例引用旧名的情况（如 `docs/tutorials/02-developer-tutorial.md` 中的 `from unifiles.core.database import DatabaseManager`），仅为文档示例，不影响运行路径。

