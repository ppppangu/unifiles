# OCR 模块（面向开发者）

模块提供统一、可扩展的 OCR 抽象，对外统一入口为 `OCRProcessor`，内部通过“抽象基类 + 工厂”解耦供应商；支持本地文件处理、目录并发处理、结果落盘（Markdown 与图片）。当前内置供应商：
- `simple`（内置 pdfplumber/PyMuPDF，基本文本+图片抽取）
- `mistral`（Mistral OCR）
- `selfhosted`（OpenAI 兼容，自部署，单实例）
- `openai`（OpenAI/GPT-4o 等，单实例）

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
│   ├── simple.py          # SimpleOCRConfig：本地内置 provider，无需凭证
│   ├── mistral.py         # MistralConfig：MISTRAL_API_KEY/MISTRAL_OCR_MODEL
│   ├── selfhosted.py      # SelfHostedConfig：单实例，OpenAI 兼容
│   └── openai.py          # OpenAIConfig：单实例，OpenAI 官方/兼容
└── providers/
    ├── simple.py          # SimpleOCRProvider：pdfplumber + PyMuPDF，内置基线
    ├── mistral.py         # MistralOCRProvider：原生异步，对接 mistralai SDK
    ├── selfhosted.py      # SelfHostedOCRProvider：OpenAI 兼容（使用 OpenAI SDK）
    └── openai.py          # OpenAIOCRProvider：OpenAI 官方/兼容（使用 OpenAI SDK）
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
  - `OCRProcessor(provider_name, config=None)`：创建并持有提供者实例。
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

### 自部署 OCR 服务（SelfHosted，单实例）

#### 环境变量配置

配置示例（.env，单实例）：

```bash
# Qwen3-VL 示例（通过 vLLM 部署）
UNIFILES_SERVICE_OCR_SELFHOSTED_URL=http://localhost:8012/v1/chat/completions
UNIFILES_SERVICE_OCR_SELFHOSTED_MODEL=qwen3vl-2b
UNIFILES_SERVICE_OCR_SELFHOSTED_PROMPT=请识别图片中的所有文字内容，包括表格、列表等结构化内容。请使用 Markdown 格式输出，保持原有的段落结构和格式。
UNIFILES_SERVICE_OCR_SELFHOSTED_TEMPERATURE=0.7       # 可选，默认 0.7
UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_TOKENS=2048       # 可选，默认 2048
```

**必需参数**：
- `URL`: OpenAI 兼容 API 端点（通常是 `/v1/chat/completions`）
- `MODEL`: 模型名称（需与 vLLM `--served-model-name` 参数一致）
- `PROMPT`: OCR 提示词

**可选参数**：
- `TEMPERATURE`: 生成温度（默认 0.7）
- `MAX_TOKENS`: 最大生成 tokens（默认 2048）

（多实例已移除，统一采用单实例配置。并发/重试/超时可通过对应环境变量调整。）

#### 使用示例

```python
from unifiles.core.ocr import OCRProcessor
from unifiles.core.ocr.config.selfhosted import SelfHostedConfig

# 方式 1: 使用默认配置（单实例）
processor = OCRProcessor('selfhosted')
text = processor.process_file('document.png')
print(text)

# 方式 2: 传入配置（单实例）
config = SelfHostedConfig()
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

### OpenAI 兼容 OCR 服务（OpenAI，单实例）

#### 概述

通用的 OpenAI 兼容 Vision API provider，支持任何符合 OpenAI Chat Completion 格式的服务，包括：
- **OpenAI 官方**: GPT-4V, GPT-4o, GPT-4-turbo
- **硅基流动 (SiliconFlow)**: Qwen2-VL, GLM-4V 等
- **通义千问 (Tongyi Qianwen)**: qwen-vl-plus, qwen-vl-max
- **其他 OpenAI 兼容服务**: 支持所有符合 OpenAI Chat Completion 格式的多模态 Vision API

#### 与 SelfHosted 的区别

| 特性 | OpenAI Provider | SelfHosted Provider |
|-----|----------------|---------------------|
| **认证方式** | ✅ 需要 API Key (Authorization: Bearer) | ❌ 无需认证 |
| **使用场景** | 云服务商 API (OpenAI, 硅基流动等) | 本地自部署模型 (vLLM 等) |
| **配置前缀** | `OPENAI_` (单实例) | `SELFHOSTED_` (单实例) |
| **并发支持** | ✅ 支持异步并行处理 | ✅ 支持异步并行处理 |
| **重试机制** | ✅ 支持自动重试 | ✅ 支持自动重试 |

#### 环境变量配置（单实例）

配置示例（.env）：

```bash
UNIFILES_SERVICE_OCR_OPENAI_URL=https://api.openai.com/v1/chat/completions
UNIFILES_SERVICE_OCR_OPENAI_API_KEY=sk-...      # Required
UNIFILES_SERVICE_OCR_OPENAI_MODEL=gpt-4o        # Required
UNIFILES_SERVICE_OCR_OPENAI_PROMPT=Extract all text content from the image and output in Markdown format
```

**必需参数**：
- `URL`: OpenAI 兼容 API 端点（通常是 `/v1/chat/completions`）
- `API_KEY`: API 密钥（用于 Authorization: Bearer 认证）
- `MODEL`: 模型名称
- `PROMPT`: OCR 提示词

为降低复杂度，OpenAI 供应商仅保留以上 4 个环境变量。并发/重试/超时等参数使用内部默认值。（多实例已移除，统一采用单实例配置）

#### 使用示例

##### 方式 1: 使用 OCRProcessor（推荐）

```python
from unifiles.core.ocr import OCRProcessor

processor = OCRProcessor('openai')
text = processor.process_file('document.pdf')
print(text)

# 单实例无需指定实例编号
```

##### 方式 2: 直接使用 Provider（异步）

```python
import asyncio
from unifiles.core.ocr.providers.openai import OpenAIOCRProvider
from unifiles.core.ocr.config.openai import OpenAIConfig

async def process_pdf():
    config = OpenAIConfig()
    provider = OpenAIOCRProvider(config)

    # 定义进度回调（可选）
    def progress_callback(page, total, status, msg):
        print(f"Page {page}/{total}: {status}")

    # 异步并行处理 PDF
    result = await provider.aprocess_file_native(
        'document.pdf',
        progress_callback=progress_callback
    )
    return result

text = asyncio.run(process_pdf())
print(text)
```

##### 方式 3: 在 FastAPI 中使用

```python
from fastapi import FastAPI
from unifiles.core.ocr.providers.openai import OpenAIOCRProvider
from unifiles.core.ocr.config.openai import OpenAIConfig

app = FastAPI()

@app.post("/ocr/process")
async def process_document(file_path: str):
    config = OpenAIConfig()
    provider = OpenAIOCRProvider(config)

    # 直接使用 await，充分利用异步特性
    result = await provider.aprocess_file_native(file_path)

    return {"content": result, "length": len(result)}
```

#### 测试脚本

```bash
# 基础测试
python test/test_openai_ocr.py sample.pdf

# 性能对比（同步 vs 异步）
python test/test_openai_ocr.py sample.pdf --compare
```

#### 性能优化

**异步并行处理** - 对于 PDF 文件，provider 会自动使用异步并行处理：
- **同步处理**: 20 页 PDF 约需 200 秒（串行处理）
- **异步并行**: 20 页 PDF 约需 50 秒（并发数=5 时）
- **加速比**: 约 4x（取决于网络延迟和服务器响应速度）

调优建议：
- 根据 API 服务商的速率限制调整 `MAX_CONCURRENCY`
- OpenAI 官方建议并发数 ≤ 10
- 国内服务商（如硅基流动）建议并发数 5-10

（消息体格式与 SelfHosted 相同，均为标准 OpenAI Chat Completions，差异在于是否需要 API Key）

（常见兼容服务：OpenAI、硅基流动、通义千问等，使用各自的兼容端点与模型名称）

#### 注意事项

- 图片会自动编码为 base64 格式
- 支持图片格式：JPEG, PNG, GIF, WebP
- PDF 文件会自动转换为图片后异步并行处理
- **需要 API Key 认证**（与 SelfHosted 的主要区别）
- URL 处理不支持（因为需要 base64 编码）
- 注意 API 调用成本和速率限制

## 扩展新的供应商（指引）

新增 Provider 时：
- 在 `config/` 下添加对应配置类（继承 `BaseConfig`）
- 在 `providers/` 下实现 `BaseOCRProvider` 协议
- 在 `factory.py` 中注册 `provider` 与 `config`

## 设计约束与默认行为

- 文件校验：默认限制大小 ≤ 10MB（`ocr/base.py:26`）。
- 支持扩展名（目录处理）：`.pdf .png .jpg .jpeg .avif .pptx .docx`（`ocr/processor.py:61`、`ocr/processor.py:118`）。
- 落盘规则：
  - Markdown：`<源目录>/<文件名>.md`
  - 图片：`<源目录>/<文件名>_images/img-{i}.jpeg`（Mistral 会返回图片，OpenAI/自部署只返回文本）
- 异步策略：
  - Base 层提供线程封装的 `aprocess_*`；
  - Mistral 覆盖为 SDK 原生 `process_async`，I/O 采用 `asyncio.to_thread` 读取。
- URL 未实现：Mistral 的 `process_url/aprocess_url` 暂未提供实现（`ocr/providers/mistral.py:73`、`132`）。

## 故障与排查

- 环境变量缺失：各 Provider 的必填项（API Key/URL/Model/Prompt）未设置会导致 `validate()` 失败
- 文件过大：超过 10MB 将在 `validate_file` 直接跳过
- 响应为空：Provider 返回空内容时将记录日志并回退为空字符串

## 相关文件索引

- `ocr/base.py:10`
- `ocr/processor.py:9`
- `ocr/factory.py:7`
- `ocr/config/base.py:8`
- `ocr/config/mistral.py`
- `ocr/config/selfhosted.py`
- `ocr/config/openai.py`
- `ocr/providers/mistral.py`
- `ocr/providers/selfhosted.py`
- `ocr/providers/openai.py`
