"""
嵌入服务
提供文本和图片的嵌入处理，支持可替换的嵌入提供者
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config.env_config import read_config


class EmbeddingProvider(Protocol):
    """嵌入提供者接口"""

    async def embed_text(self, text: str) -> List[float]:
        """嵌入文本"""
        ...

    async def embed_image_description(self, image_url: str) -> Tuple[str, List[float]]:
        """嵌入图片"""
        ...

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        ...

    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        ...


class SingletonEmbeddingProvider:
    """单例嵌入提供者 - 基于现有的singleton_embedding.py逻辑"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or read_config()
        self.provider_name = "singleton_embedding"
        self.embedding_dimension = 1024  # 默认维度，应该从配置或实际模型获取

    def get_provider_name(self) -> str:
        return self.provider_name

    def get_embedding_dimension(self) -> int:
        return self.embedding_dimension

    def _get_latest_embedding_instance(
        self, instance_type: Optional[str] = None, alias: Optional[str] = None
    ):
        """获取最新的嵌入实例配置（模拟singleton_embedding.py的逻辑）"""
        # 这里应该实现实际的单例逻辑，现在提供模拟实现
        if alias:
            # 根据alias获取特定配置
            if alias == "bge-m3":
                return (
                    "bge-m3",
                    "http://localhost:8080/v1/embeddings",
                    "your-api-key",
                    "bge-m3",
                )
            if alias == "text-embedding-ada-002":
                return (
                    "text-embedding-ada-002",
                    "https://api.openai.com/v1/embeddings",
                    "your-openai-key",
                    "text-embedding-ada-002",
                )

        if instance_type == "language_embedding":
            return (
                "bge-m3",
                "http://localhost:8080/v1/embeddings",
                "your-api-key",
                "bge-m3",
            )
        if instance_type == "multimodal_llm":
            return (
                "gpt-4-vision",
                "http://localhost:8081/v1/chat/completions",
                "your-api-key",
                "gpt-4-vision",
            )

        # 默认返回
        return "bge-m3", "http://localhost:8080/v1/embeddings", "your-api-key", "bge-m3"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.RequestError, httpx.HTTPStatusError, httpx.ProtocolError)
        ),
    )
    async def embed_text(self, text: str, alias: str = "bge-m3") -> List[float]:
        """嵌入文本"""
        try:
            name, url, key, _ = self._get_latest_embedding_instance(alias=alias)

            # 准备请求头
            headers = {}
            if key and key.strip():
                headers["Authorization"] = f"Bearer {key}"

            # 配置HTTP客户端
            timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)
            limits = httpx.Limits(
                max_keepalive_connections=10, max_connections=50, keepalive_expiry=30.0
            )

            async with httpx.AsyncClient(
                timeout=timeout, limits=limits, http2=False, verify=False
            ) as client:
                response = await client.post(
                    url, headers=headers, json={"model": name, "input": text}
                )
                response.raise_for_status()
                result = response.json()

                if (
                    "data" in result
                    and len(result["data"]) > 0
                    and "embedding" in result["data"][0]
                ):
                    embedding = result["data"][0]["embedding"]
                    logger.debug(
                        f"Text embedding successful, dimension: {len(embedding)}"
                    )
                    return embedding
                logger.error(f"Invalid embedding response format: {result}")
                raise ValueError("Invalid embedding response format")

        except Exception as e:
            logger.error(f"Text embedding failed: {e!s}, URL: {url}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.RequestError, httpx.HTTPStatusError, httpx.ProtocolError)
        ),
    )
    async def describe_image(self, image_url: str, alias: str = "") -> str:
        """描述图片内容"""
        try:
            if not alias:
                name, url, key, alias = self._get_latest_embedding_instance(
                    instance_type="multimodal_llm"
                )
            else:
                name, url, key, alias = self._get_latest_embedding_instance(alias=alias)

            # 准备请求头
            headers = {}
            if key and key.strip():
                headers["Authorization"] = f"Bearer {key}"

            data = {
                "model": name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请详细描述这张图片的内容"}
                        ],
                    },
                ],
                "stream": False,
            }

            timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)
            limits = httpx.Limits(
                max_keepalive_connections=10, max_connections=50, keepalive_expiry=30.0
            )

            async with httpx.AsyncClient(
                timeout=timeout, limits=limits, http2=False, verify=False
            ) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    description = result["choices"][0]["message"]["content"]
                    logger.debug(
                        f"Image description successful, length: {len(description)}"
                    )
                    return description
                logger.error(f"Invalid image description response: {result}")
                raise ValueError("Invalid image description response")

        except Exception as e:
            logger.error(f"Image description failed: {e!s}, URL: {url}")
            raise

    async def embed_image_description(
        self, image_url: str, alias: str = "bge-m3"
    ) -> Tuple[str, List[float]]:
        """嵌入图片：先描述图片，再对描述进行嵌入"""
        try:
            # 先获取图片描述
            description = await self.describe_image(image_url)

            # 再对描述进行嵌入
            embedding = await self.embed_text(description, alias)

            logger.debug(
                f"Image embedding successful: description length={len(description)}, embedding dimension={len(embedding)}"
            )
            return description, embedding

        except Exception as e:
            logger.error(f"Image embedding failed: {e!s}")
            raise


class EmbeddingService:
    """嵌入服务主类"""

    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or read_config()
        self.provider = provider or SingletonEmbeddingProvider(config)

    def set_provider(self, provider: EmbeddingProvider):
        """设置嵌入提供者（支持运行时替换）"""
        self.provider = provider
        logger.info(f"Embedding provider changed to: {provider.get_provider_name()}")

    async def embed_single_text(self, text: str) -> List[float]:
        """嵌入单个文本"""
        return await self.provider.embed_text(text)

    async def embed_single_image(self, image_url: str) -> Tuple[str, List[float]]:
        """嵌入单个图片"""
        return await self.provider.embed_image_description(image_url)

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "provider": self.provider.get_provider_name(),
            "embedding_dimension": self.provider.get_embedding_dimension(),
            "concurrency_limit": self.batch_processor.concurrency_limit,
            "supported_types": ["text", "image"],
        }


# 默认嵌入服务实例
_default_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(config: Optional[Dict[str, Any]] = None) -> EmbeddingService:
    """获取默认嵌入服务实例（单例模式）"""
    global _default_embedding_service
    if _default_embedding_service is None:
        _default_embedding_service = EmbeddingService(config=config)
    return _default_embedding_service


def set_global_embedding_provider(provider: EmbeddingProvider):
    """设置全局嵌入提供者"""
    service = get_embedding_service()
    service.set_provider(provider)
