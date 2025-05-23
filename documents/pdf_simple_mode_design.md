## 简易模式（simple）整体设计文档

### 1. 背景说明
当前 `upload_server原始的` 中的实现存在以下痛点：
1. 内存泄漏、阻塞严重；
2. 仅支持本地文件上传，无法处理公网 PDF 链接；
3. 数据库存取逻辑未适配最新的层级表设计；
4. 缺乏统一的任务状态管理；

本次重构目标是在 **保持接口不变** 的前提下：
* 新增 `pdf_file_url` 参数，支持异步下载处理；
* 兼容旧接口 (`pdf_file` 仍可上传)；
* 若 `job_id` 未携带则自动生成；
* `mode` 默认为 `simple`，后续可扩展其它模式；
* 处理流程完全异步化，CPU 密集逻辑全部包裹 `asyncio.to_thread`；
* 数据表操作兼容最新的 **users ⇄ knowledge_bases ⇄ documents ⇄ chunks** 触发器链；

### 2. 端点设计
| 路径 | 方法 | 入参 | 说明 |
|------|------|------|------|
| `/process-pdf/` | POST | `knowledge_base_id:str`、`document_id:str`、`pdf_file_url:str(可选)`、`pdf_file:UploadFile(可选)`、`job_id:str(可选)`、`mode:str=\"simple\"` | 返回 `{status, job_id}`，请求收到即排队后台处理 |
| `/jobs/{job_id}` | GET  | 无 | 查询任务 `status/result`（预留,本迭代可返回 *todo*） |
| `/health` | GET | – | 健康检查 |

### 3. 处理流程（simple 模式）
```mermaid
flowchart TD
    A[接收请求] -->|生成 job_id\n保存队列| B
    B -->|aiohttp 下载 PDF| C
    C -->|to_thread 解析 pdfplumber| D
    D -->|detect img/table| E{是否含多模态元素?}
    E -->|是| F[截图 + base64 调 multimodal LLM\n得到描述页 BytesIO]
    E -->|否| G
    F --> to_thread --> H[合成新 PDF (原页+描述页)]
    G --> H
    H -->|提取纯文本| I
    I -->|滑窗分块| J[create_chunks]
    J -->|并发 get_embedding_async| K
    K -->|批量插入 chunks| L[PGVector]
    L -->|更新任务状态| M[完成]
```

### 4. 核心模块拆分
1. `db.py`          – 连接池与表初始化 helper；
2. `models.py`      – `@dataclass` 持久化 DTO；
3. `tasks.py`       – `async def simple_pipeline(**kwargs)`；
4. `pdf_utils.py`   – 下载、图片检测、OCR 汇总工具；
5. `chunks.py`      – 分块 + 嵌入；
6. `main.py`        – FastAPI 入口文件；

### 5. 第一期实现范围
- [x] 设计文档产出（当前文件）
- [ ] checklist 初始版本
- [ ] FastAPI skeleton (`src/main.py`)
- [ ] 简易任务队列（内存 dict）
- [ ] aiohttp 下载
- [ ] pdfplumber 提取 + 简单 detect
- [ ] embedding 调用（singleton）
- [ ] 新表插入逻辑兼容
- [ ] 单元测试 stub

### 6. 关键外部依赖
- fastapi / uvicorn
- aiohttp
- pdfplumber / PyPDF2 / reportlab / opencv-python-headless
- psycopg2-binary / asyncpg (后续可换异步池)

### 7. 风险点
1. **Windows + ARM** 部署差异 – opencv & pdfplumber 的编译依赖需提前验证；
2. **多模态 LLM** 调用速率限制；
3. **大文件 PDF** 内存峰值控制；
4. 数据插入触发器竞态 – 首次写入需包装事务；

### 8. 里程碑
| 序号 | 里程碑 | 预计完成 |
|------|--------|----------|
| 1 | skeleton 跑通 + 下载 | D1 |
| 2 | detect & ocr 汇总 | D2 |
| 3 | 分块 + pgvector 写入 | D3 |
| 4 | 全流程 e2e 测试 | D4 | 