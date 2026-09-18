# 自定义 OCR 提供者

本教程讲解如何在自部署环境中集成自定义 OCR 提供者，以满足特定的识别需求或成本优化目标。

## OCR 提供者概述

Unifiles 支持多种 OCR 提供者：

| 提供者 | 说明 | 适用场景 |
|-------|------|---------|
| `default` | 系统默认引擎 | 通用场景 |
| `tesseract` | 开源 Tesseract | 自部署、成本敏感 |
| `paddleocr` | 百度 PaddleOCR | 中文优化 |
| `cloud` | 云端高精度 OCR | 复杂文档 |
| `custom` | 自定义提供者 | 特殊需求 |

## 使用内置提供者

### 指定 OCR 提供者

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>")

# 使用 Tesseract（开源）
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "ocr_provider": "tesseract",
        "language": "chi_sim"  # Tesseract 语言代码
    }
)

# 使用 PaddleOCR（中文优化）
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "ocr_provider": "paddleocr",
        "language": "ch"
    }
)

# 使用云端 OCR（最高精度）
extraction = client.extractions.create(
    file_id=file.id,
    mode="advanced",
    options={
        "ocr_provider": "cloud",
        "language": "zh"
    }
)
```

### 提供者对比

```python
def compare_ocr_providers(file_id: str):
    """对比不同 OCR 提供者的效果"""
    
    providers = ["tesseract", "paddleocr", "cloud"]
    results = {}
    
    for provider in providers:
        try:
            extraction = client.extractions.create(
                file_id=file_id,
                mode="advanced",
                options={"ocr_provider": provider}
            )
            extraction.wait()
            
            results[provider] = {
                "status": extraction.status,
                "content_length": len(extraction.markdown),
                "processing_time": extraction.processing_time
            }
        except Exception as e:
            results[provider] = {"status": "error", "error": str(e)}
    
    return results

# 对比结果
results = compare_ocr_providers(file.id)
for provider, result in results.items():
    print(f"{provider}: {result}")
```

## 自部署：配置 OCR 提供者

### 环境变量配置

```bash
# .env 文件

# 默认 OCR 提供者
OCR_DEFAULT_PROVIDER=paddleocr

# Tesseract 配置
TESSERACT_PATH=/usr/bin/tesseract
TESSERACT_DATA_PATH=/usr/share/tesseract-ocr/4.00/tessdata

# PaddleOCR 配置
PADDLEOCR_USE_GPU=true
PADDLEOCR_MODEL_DIR=/models/paddleocr

# 云端 OCR 配置（如果使用）
CLOUD_OCR_ENDPOINT=https://ocr.example.com/api
CLOUD_OCR_API_KEY=your_cloud_ocr_key
```

### Docker 配置

```yaml
# docker-compose.yml
services:
  unifiles:
    image: unifiles/server:latest
    environment:
      - OCR_DEFAULT_PROVIDER=paddleocr
      - PADDLEOCR_USE_GPU=false
    volumes:
      - ./tessdata:/usr/share/tesseract-ocr/tessdata
      - ./paddleocr_models:/models/paddleocr
```

## 实现自定义 OCR 提供者

### 步骤1：创建提供者类

```python
# custom_ocr_provider.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class OCRResult:
    text: str
    confidence: float
    metadata: Dict[str, Any]

class BaseOCRProvider(ABC):
    """OCR 提供者基类"""
    
    @abstractmethod
    def recognize(
        self,
        image_path: str,
        language: str = "en",
        options: Optional[Dict] = None
    ) -> OCRResult:
        """识别图片中的文字"""
        pass
    
    @abstractmethod
    def recognize_pdf(
        self,
        pdf_path: str,
        language: str = "en",
        options: Optional[Dict] = None
    ) -> list[OCRResult]:
        """识别 PDF 中的文字（按页返回）"""
        pass


class CustomCloudOCR(BaseOCRProvider):
    """自定义云端 OCR 提供者示例"""
    
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
    
    def recognize(
        self,
        image_path: str,
        language: str = "en",
        options: Optional[Dict] = None
    ) -> OCRResult:
        import requests
        
        with open(image_path, "rb") as f:
            response = requests.post(
                f"{self.endpoint}/recognize",
                files={"image": f},
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"language": language}
            )
        
        result = response.json()
        
        return OCRResult(
            text=result["text"],
            confidence=result["confidence"],
            metadata={"provider": "custom_cloud"}
        )
    
    def recognize_pdf(
        self,
        pdf_path: str,
        language: str = "en",
        options: Optional[Dict] = None
    ) -> list[OCRResult]:
        # 将 PDF 转为图片，逐页识别
        from pdf2image import convert_from_path
        import tempfile
        
        results = []
        images = convert_from_path(pdf_path)
        
        for i, image in enumerate(images):
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                image.save(tmp.name)
                result = self.recognize(tmp.name, language, options)
                result.metadata["page"] = i + 1
                results.append(result)
        
        return results
```

### 步骤2：注册提供者

```python
# ocr_registry.py
from typing import Dict, Type
from custom_ocr_provider import BaseOCRProvider

class OCRProviderRegistry:
    """OCR 提供者注册表"""
    
    _providers: Dict[str, Type[BaseOCRProvider]] = {}
    _instances: Dict[str, BaseOCRProvider] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: Type[BaseOCRProvider]):
        """注册 OCR 提供者"""
        cls._providers[name] = provider_class
    
    @classmethod
    def get(cls, name: str, **kwargs) -> BaseOCRProvider:
        """获取 OCR 提供者实例"""
        if name not in cls._instances:
            if name not in cls._providers:
                raise ValueError(f"Unknown OCR provider: {name}")
            
            cls._instances[name] = cls._providers[name](**kwargs)
        
        return cls._instances[name]

# 注册内置提供者
from builtin_providers import TesseractOCR, PaddleOCR

OCRProviderRegistry.register("tesseract", TesseractOCR)
OCRProviderRegistry.register("paddleocr", PaddleOCR)

# 注册自定义提供者
from custom_ocr_provider import CustomCloudOCR

OCRProviderRegistry.register("custom_cloud", CustomCloudOCR)
```

### 步骤3：在提取流程中使用

```python
# extraction_service.py
from ocr_registry import OCRProviderRegistry

class ExtractionService:
    def __init__(self, default_ocr_provider: str = "paddleocr"):
        self.default_ocr = default_ocr_provider
    
    def extract_content(
        self,
        file_path: str,
        ocr_provider: str = None,
        language: str = "zh",
        options: dict = None
    ) -> str:
        """提取文件内容"""
        
        provider_name = ocr_provider or self.default_ocr
        
        # 获取 OCR 提供者
        ocr = OCRProviderRegistry.get(
            provider_name,
            endpoint=os.getenv("CUSTOM_OCR_ENDPOINT"),
            api_key=os.getenv("CUSTOM_OCR_API_KEY")
        )
        
        # 根据文件类型处理
        if file_path.endswith(".pdf"):
            results = ocr.recognize_pdf(file_path, language, options)
            return self._merge_results(results)
        else:
            result = ocr.recognize(file_path, language, options)
            return result.text
    
    def _merge_results(self, results: list) -> str:
        """合并多页结果为 Markdown"""
        markdown = ""
        for result in results:
            page = result.metadata.get("page", "?")
            markdown += f"\n\n<!-- Page {page} -->\n\n"
            markdown += result.text
        return markdown.strip()
```

## 配置示例

### 使用腾讯云 OCR

```python
class TencentCloudOCR(BaseOCRProvider):
    """腾讯云 OCR 提供者"""
    
    def __init__(self, secret_id: str, secret_key: str, region: str = "ap-guangzhou"):
        from tencentcloud.common import credential
        from tencentcloud.ocr.v20181119 import ocr_client
        
        cred = credential.Credential(secret_id, secret_key)
        self.client = ocr_client.OcrClient(cred, region)
    
    def recognize(self, image_path: str, language: str = "zh", options=None) -> OCRResult:
        from tencentcloud.ocr.v20181119 import models
        import base64
        
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        req = models.GeneralBasicOCRRequest()
        req.ImageBase64 = image_base64
        
        resp = self.client.GeneralBasicOCR(req)
        
        text = "\n".join([item.DetectedText for item in resp.TextDetections])
        
        return OCRResult(
            text=text,
            confidence=sum(item.Confidence for item in resp.TextDetections) / len(resp.TextDetections),
            metadata={"provider": "tencent_cloud"}
        )

# 注册
OCRProviderRegistry.register("tencent", TencentCloudOCR)
```

### 使用阿里云 OCR

```python
class AliyunOCR(BaseOCRProvider):
    """阿里云 OCR 提供者"""
    
    def __init__(self, access_key_id: str, access_key_secret: str):
        from alibabacloud_ocr_api20210707.client import Client
        from alibabacloud_tea_openapi import models as open_api_models
        
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint="ocr-api.cn-hangzhou.aliyuncs.com"
        )
        self.client = Client(config)
    
    def recognize(self, image_path: str, language: str = "zh", options=None) -> OCRResult:
        from alibabacloud_ocr_api20210707 import models
        
        with open(image_path, "rb") as f:
            req = models.RecognizeGeneralRequest(body=f)
            resp = self.client.recognize_general(req)
        
        return OCRResult(
            text=resp.body.data.content,
            confidence=0.95,  # 阿里云 API 返回格式不同
            metadata={"provider": "aliyun"}
        )

# 注册
OCRProviderRegistry.register("aliyun", AliyunOCR)
```

## 最佳实践

### 1. 根据文档类型选择提供者

```python
def select_ocr_provider(file_info: dict) -> str:
    """智能选择 OCR 提供者"""
    
    # 中文文档优先使用 PaddleOCR
    if file_info.get("language") == "zh":
        return "paddleocr"
    
    # 高价值文档使用云端 OCR
    if file_info.get("priority") == "high":
        return "cloud"
    
    # 默认使用 Tesseract
    return "tesseract"
```

### 2. 实现失败回退

```python
def extract_with_fallback(file_path: str, providers: list = None):
    """带回退的 OCR 提取"""
    
    providers = providers or ["paddleocr", "tesseract", "cloud"]
    
    for provider in providers:
        try:
            result = extract_content(file_path, ocr_provider=provider)
            if result and len(result) > 100:  # 基本验证
                return result
        except Exception as e:
            print(f"{provider} 失败: {e}")
            continue
    
    raise Exception("所有 OCR 提供者均失败")
```

### 3. 缓存 OCR 结果

```python
import hashlib

def get_cached_ocr(file_path: str) -> Optional[str]:
    """获取缓存的 OCR 结果"""
    file_hash = hashlib.md5(open(file_path, "rb").read()).hexdigest()
    cache_key = f"ocr:{file_hash}"
    return redis_client.get(cache_key)

def cache_ocr_result(file_path: str, result: str, ttl: int = 86400):
    """缓存 OCR 结果"""
    file_hash = hashlib.md5(open(file_path, "rb").read()).hexdigest()
    cache_key = f"ocr:{file_hash}"
    redis_client.setex(cache_key, ttl, result)
```

## 下一步

- [性能调优](performance-tuning.md) - OCR 性能优化
- [自部署指南](../../self-hosting/index.md) - 完整部署文档
- [内容提取](../../using-the-api/content-extraction.md) - 提取 API 参考
