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
    ├── mistral.py         # MistralOCRProvider：具体实现（含原生异步）
    └── selfhosted.py      # SelfHostedOCRProvider：自部署HTTP服务对接
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

环境变量（.env，必填项）：

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

### 自部署 OCR 服务（SelfHosted）

#### 环境变量配置

配置示例（.env）：

```bash
# Qwen3-VL 示例（通过 vLLM 部署）
UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL=http://localhost:8012/v1/chat/completions
UNIFILES_SERVICE_OCR_SELFHOSTED_0_MODEL=qwen3vl-2b
UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT=请识别图片中的所有文字内容，包括表格、列表等结构化内容。请使用 Markdown 格式输出，保持原有的段落结构和格式。
UNIFILES_SERVICE_OCR_SELFHOSTED_0_TEMPERATURE=0.7       # 可选，默认 0.7
UNIFILES_SERVICE_OCR_SELFHOSTED_0_MAX_TOKENS=2048       # 可选，默认 2048
```

**必需参数**：
- `URL`: OpenAI 兼容 API 端点（通常是 `/v1/chat/completions`）
- `MODEL`: 模型名称（需与 vLLM `--served-model-name` 参数一致）
- `PROMPT`: OCR 提示词

**可选参数**：
- `TEMPERATURE`: 生成温度（默认 0.7）
- `MAX_TOKENS`: 最大生成 tokens（默认 2048）

#### 多实例配置

支持配置多个实例（实例编号：0, 1, 2, ...）：

```bash
# 实例 0: Qwen3-VL 2B
UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL=http://localhost:8012/v1/chat/completions
UNIFILES_SERVICE_OCR_SELFHOSTED_0_MODEL=qwen3vl-2b
UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT=请识别文字并输出 Markdown

# 实例 1: Qwen2-VL 7B
UNIFILES_SERVICE_OCR_SELFHOSTED_1_URL=http://192.168.1.100:8013/v1/chat/completions
UNIFILES_SERVICE_OCR_SELFHOSTED_1_MODEL=qwen2-vl-7b
UNIFILES_SERVICE_OCR_SELFHOSTED_1_PROMPT=Extract all text with structure
```

#### 使用示例

```python
from unifiles.core.ocr import OCRProcessor
from unifiles.core.ocr.config.selfhosted import SelfHostedConfig

# 方式 1: 使用默认实例（实例 0）
processor = OCRProcessor('selfhosted')
text = processor.process_file('document.png')
print(text)

# 方式 2: 指定实例编号
config = SelfHostedConfig(instance_id=1)
processor = OCRProcessor('selfhosted', config=config)
text = processor.process_file('image.jpg')
print(text)

# 支持 PDF（自动分页处理）
text = processor.process_file('report.pdf')
```

#### 技术细节

**请求格式**：OpenAI Chat Completion 格式
```json
{
  "model": "qwen3vl-2b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
      {"type": "text", "text": "请识别图片中的文字..."}
    ]
  }],
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false
}
```

**响应格式**：标准 OpenAI 响应
```json
{
  "choices": [{
    "message": {
      "content": "识别的文字内容..."
    }
  }]
}
```

**注意事项**：
- 图片会自动编码为 base64 格式
- 支持图片格式：JPEG, PNG, GIF, WebP
- PDF 文件会自动转换为图片后逐页处理
- 无需认证（如需认证，请在服务端实现）
- URL 处理不支持（因为需要 base64 编码）

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
