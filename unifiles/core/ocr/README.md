# OCR 模块（面向开发者）

模块提供统一、可扩展的 OCR 抽象，当前内置 Mistral 实现。对外统一入口为 `OCRProcessor`，内部通过“抽象基类 + 工厂”解耦供应商；支持本地文件处理、目录并发处理、结果落盘（Markdown 与图片），并保留旧接口兼容。

## 架构总览

- 核心入口：`OCRProcessor` 统一对外 API（文件/URL/目录、同步/异步）。
- 提供者契约：各供应商实现 `BaseOCRProvider` 约定的方法与持久化接口。
- 配置解耦：`BaseConfig` 负责环境与模型配置，供应商自定义实现（如 `MistralConfig`）。
- 工厂创建：`OCRProviderFactory` 统一创建/注册供应商实例，可运行时切换。

目录结构：

```
ocr/
├── __init__.py
├── base.py                # BaseOCRProvider：统一契约 + 通用校验/落盘 + 异步包装
├── factory.py             # OCRProviderFactory：创建/注册/查询
├── processor.py           # OCRProcessor：统一入口 + 目录并发
├── config/
│   ├── base.py            # BaseConfig：加载 .env，定义 validate/getters
│   └── mistral.py         # MistralConfig：MISTRAL_API_KEY/MISTRAL_OCR_MODEL
└── providers/
    └── mistral.py         # MistralOCRProvider：具体实现（含原生异步）
```

## API 与契约

- Base 提供者（实现者需遵守）
  - `process_file(file_path) -> str`：处理本地文件，返回 Markdown。
  - `process_url(url) -> str`：处理 URL（按需实现）。
  - `validate_file(file_path) -> bool`：通用校验（存在性、大小 ≤ 10MB）。
  - `save_to_markdown(text, output_path, title=None)`：保存 Markdown。
  - `save_to_images(images, output_dir=None)`：保存图片（实现方决定格式）。
  - 异步默认实现：`aprocess_file/url`、`asave_to_*` 为线程封装，具体提供者可覆盖为“原生异步”。

- 统一入口（使用方）
  - `OCRProcessor(provider_name='mistral', config=None)`：创建并持有提供者实例。
  - `process_file(file)` / `aprocess_file(file)`：处理单文件。
  - `process_directory(dir, exts=None)` / `aprocess_directory(dir, exts=None, concurrency=5)`：处理目录（并发）。
  - `switch_provider(name, config=None)`：运行时切换供应商。
  - `get_supported_providers()`：查询已注册供应商。

## Mistral 实现要点

- 客户端与调用：
  - 同步：`client.ocr.process(...)`
  - 异步：`await client.ocr.process_async(...)`（Provider 已覆盖为原生异步）。
- 输入：将文件内容 `base64` 后以 `data:application/pdf;base64,<...>` 形式传入。
- 输出：
  - Markdown：按页拼接，页间以 `---` 分隔；落盘到与源文件同名的 `*.md`。
  - 图片：`<源文件名>_images/img-{i}.jpeg`。
- URL 能力：`process_url/aprocess_url` 暂未实现（抛出 `NotImplementedError`）。

参考实现：
- 提供者：`ocr/providers/mistral.py:13`
- 基类：`ocr/base.py:10`
- 处理器：`ocr/processor.py:9`
- 工厂：`ocr/factory.py:7`
- 配置：`ocr/config/mistral.py:6`，`ocr/config/base.py:8`

## 使用示例

环境变量（.env）：

```
MISTRAL_API_KEY=your_api_key_here
MISTRAL_OCR_MODEL=mistral-ocr-latest  # 可选
```

同步与异步：

```python
from ocr import OCRProcessor

processor = OCRProcessor('mistral')

# 同步：单文件
text = processor.process_file('samples/gpt-paper.pdf')

# 异步：单文件
import asyncio

async def main():
    t = await processor.aprocess_file('samples/gpt-paper.pdf')
    print(len(t))

asyncio.run(main())
```

运行示例脚本：

```
python example_new_architecture.py
```

文件保存位置：
- Markdown：`samples/gpt-paper.md`
- 图片：`samples/gpt-paper_images/img-{i}.jpeg`

## 扩展新的供应商（示例）

1) 定义配置：`ocr/config/openai.py`

```python
from .base import BaseConfig

class OpenAIConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self.api_key = self._get_env_var('OPENAI_API_KEY')
        self.model = self._get_env_var('OPENAI_OCR_MODEL', 'gpt-ocr-latest')

    def validate(self) -> bool: return bool(self.api_key)
    def get_api_key(self) -> str: return self.api_key
    def get_model(self) -> str: return self.model
```

2) 实现提供者：`ocr/providers/openai.py`

```python
from ..base import BaseOCRProvider
from ..config.openai import OpenAIConfig

class OpenAIOCRProvider(BaseOCRProvider):
    def __init__(self, config: OpenAIConfig | None = None):
        super().__init__(config or OpenAIConfig())

    def process_file(self, file_path):
        raise NotImplementedError

    def process_url(self, url: str) -> str:
        raise NotImplementedError

    def _extract_data_from_response(self, response):
        raise NotImplementedError

    def save_to_images(self, images, output_dir=None):
        raise NotImplementedError
```

3) 在工厂注册：`ocr/factory.py`

```python
from .providers.openai import OpenAIOCRProvider
from .config.openai import OpenAIConfig

_providers['openai'] = OpenAIOCRProvider
_configs['openai'] = OpenAIConfig
```

## 设计约束与默认行为

- 文件校验：默认限制大小 ≤ 10MB（`ocr/base.py:26`）。
- 支持扩展名（目录处理）：`.pdf .png .jpg .jpeg .avif .pptx .docx`（`ocr/processor.py:61`、`ocr/processor.py:118`）。
- 落盘规则：
  - Markdown：`<源目录>/<文件名>.md`（`ocr/providers/mistral.py:65`）。
  - 图片：`<源目录>/<文件名>_images/img-{i}.jpeg`（`ocr/providers/mistral.py:164` 及以下）。
- 异步策略：
  - Base 层提供线程封装的 `aprocess_*`；
  - Mistral 覆盖为 SDK 原生 `process_async`，I/O 采用 `asyncio.to_thread` 读取。
- URL 未实现：Mistral 的 `process_url/aprocess_url` 暂未提供实现（`ocr/providers/mistral.py:73`、`132`）。

## 故障与排查

- 未设置密钥：`MISTRAL_API_KEY` 缺失会在 `MistralConfig.validate()` 处报错并终止（`ocr/config/mistral.py:14`）。
- 文件过大：超过 10MB 将在 `validate_file` 直接跳过。
- 响应为空：当未返回任何 `pages.markdown` 时将返回空字符串并记录日志（`ocr/providers/mistral.py:156` 及附近）。

## 相关文件索引

- `ocr/base.py:10`
- `ocr/processor.py:9`
- `ocr/factory.py:7`
- `ocr/config/base.py:8`
- `ocr/config/mistral.py:6`
- `ocr/providers/mistral.py:13`
