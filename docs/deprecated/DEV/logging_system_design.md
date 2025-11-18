# 日志系统设计文档

本文档深入分析了 `unifiles` 项目的日志系统设计与实现。

## 1. 核心组件与技术栈

项目的日志系统基于以下核心技术构建：

- **核心库**: [**Loguru**](https://github.com/Delgan/loguru)
  - 选择 Loguru 是因为它提供了开箱即用的强大功能，如简洁的 API、颜色标记、文件滚动、线程/进程安全以及结构化日志记录。
- **设计模式**:
  - **抽象基类 (ABC)**: 定义了 `BaseLogger` 接口，统一了日志记录方法（`info`, `error` 等），使得未来可以轻松替换或扩展新的日志实现（例如，数据库日志）。
  - **工厂模式**: `init_logger` 函数作为一个工厂，根据传入的参数创建不同类型的日志记录器实例。
  - **单例模式**: 通过 `get_logger` 函数提供一个全局唯一的日志记录器实例，确保整个应用共享相同的日志配置。

## 2. 架构设计

日志系统设计分为三个层次：抽象层、实现层和访问层。

```mermaid
graph TD
    subgraph 访问层 (Application Code)
        A[其他模块, e.g., main.py, services] --> B{get_logger()};
    end

    subgraph 核心层 (core.logging.logging)
        B --> C[全局 app_logger 实例];
        D[init_logger()] -- 创建 --> C;
        
        subgraph 实现层
            E[LoguruLogger] -- 实现 --> F(BaseLogger);
            G[PostgreSQLLogger] -- (占位) --> F;
            H[HybridLogger] -- (占位) --> F;
        end

        D -- 根据配置选择 --> E;
    end

    style F fill:#f9f,stroke:#333,stroke-width:2px
```

- **抽象层 (`BaseLogger`)**: 定义了所有日志记录器必须遵守的统一接口。
- **实现层 (`LoguruLogger`, `PostgreSQLLogger`)**:
  - `LoguruLogger` 是当前的核心实现，负责处理所有日志记录逻辑，包括输出到控制台和文件。
  - `PostgreSQLLogger` 和 `HybridLogger` 是为未来功能（如将日志写入数据库）预留的占位符，体现了设计的可扩展性。
- **访问层 (`get_logger`, `init_logger`)**:
  - `init_logger`: 在应用启动时被调用，用于根据配置初始化全局日志记录器。
  - `get_logger`: 在应用的任何地方被调用，以获取已配置好的全局日志实例。

## 3. 初始化流程

日志系统的生命周期与 FastAPI 应用的生命周期绑定。

1.  **启动**: 应用在 `unifiles/app/main.py` 的 `lifespan` 管理器中启动。
2.  **调用 `init_logger`**: `lifespan` 函数内部调用 `init_logger("loguru")`，配置优先从环境变量读取（见“环境变量”）。
3.  **创建实例**: `init_logger` 创建一个 `LoguruLogger` 实例，并将其赋值给全局变量 `app_logger`。
4.  **配置 Sinks**: `LoguruLogger` 在其 `_setup` 方法中配置了两个输出目标 (Sink)：
    - **控制台 Sink**: 用于在开发过程中实时显示带颜色的日志。
    - **文件 Sink**: 用于将日志持久化到磁盘文件。
5.  **应用中使用**: 应用各模块通过调用 `get_logger()` 获取该实例并记录日志。
6.  **关闭**: 应用关闭时，`lifespan` 调用 `cleanup_logger()` 来移除 Loguru 的处理器，释放资源。

```mermaid
sequenceDiagram
    participant App as FastAPI App
    participant Main as main.py (lifespan)
    participant Factory as init_logger()
    participant Logger as LoguruLogger
    participant Loguru as Loguru Core

    App->>+Main: 启动
    Main->>+Factory: init_logger("loguru", config...)
    Factory->>+Logger: 创建 LoguruLogger 实例
    Logger->>+Loguru: logger.remove()
    Loguru-->>-Logger: 移除默认 Sink
    Logger->>+Loguru: logger.add(console_sink)
    Loguru-->>-Logger: 添加控制台 Sink
    Logger->>+Loguru: logger.add(file_sink)
    Loguru-->>-Logger: 添加文件 Sink
    Logger-->>-Factory: 返回实例
    Factory-->>-Main: 全局实例已设置
    Main-->>-App: 初始化完成
```

## 4. 详细配置

日志配置现由环境变量驱动，`main.py` 不再硬编码参数。核心变量：

- `UNIFILES_SERVICE_NAME`: 服务名称（默认 `unifiles-v1`）。
- `UNIFILES_API_LOG_LEVEL`: 日志级别（默认 `INFO`）。
- `UNIFILES_API_LOG_DIR`: 日志目录（默认项目根目录下 `logs/`）。
- `UNIFILES_API_LOG_ROTATION`: 文件滚动策略（默认 `100 MB`）。
- `UNIFILES_API_LOG_RETENTION`: 文件保留策略（默认 `30 days`）。
- `UNIFILES_API_LOG_COMPRESSION`: 压缩格式（默认 `zip`）。

格式：
- 控制台：`[时间] | [级别] | [模块:函数:行号] | [消息]`（带颜色）。
- 文件：`{时间} | {级别} | {模块:函数:行号} | {消息}`。

## 5. 使用方式

在项目中的任何模块，推荐使用统一入口获取日志：

```python
from unifiles.core.logging import get_logger

log = get_logger()

def my_function():
    log.info("这是一条信息日志。")
    log.warning("这是一条警告日志。")
    try:
        result = 1 / 0
    except ZeroDivisionError:
        log.exception("发生了一个错误！")
```
说明：直接 `from loguru import logger` 仍可工作，但为了上下文一致（例如 service 字段、未来切换实现），建议统一通过 `get_logger()`。

## 6. 总结与展望

### 当前设计优点
- **结构清晰**: 通过抽象层和实现层分离，设计清晰，易于理解和维护。
- **功能强大**: 借助 Loguru，轻松实现了结构化日志、文件滚动、压缩等高级功能。
- **使用便捷**: 全局单例模式让开发者可以方便地在任何地方记录日志。

### 可改进之处
- **细粒度过滤**: 如需按 `service` 过滤，可以在 `LoguruLogger` 内启用对应 filter；目前为兼容历史直接引用 loguru 的用法而关闭。
- **数据库日志**: `PostgreSQLLogger` 目前是占位符。在需要对日志进行复杂查询和分析的场景下，可以完成该类的实现，将关键日志（如 `ERROR` 和 `CRITICAL` 级别的日志）存入数据库。
