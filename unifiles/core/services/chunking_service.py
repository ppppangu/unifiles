"""
文档分块服务
提供多种分块策略，用于将Markdown文档分割成适合向量化的片段
"""

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from unifiles.core.logging import get_logger

logger = get_logger()


class ChunkingStrategy(Enum):
    """分块策略枚举"""

    MARKDOWN_HIERARCHICAL = "markdown_hierarchical"  # 按标题层级分割
    FIXED_SIZE = "fixed"  # 固定大小分割
    SEMANTIC = "semantic"  # 语义边界分割（句子级别）


# 全局分块器注册表
_CHUNKER_REGISTRY: Dict[str, Type["BaseChunker"]] = {}


def register_chunker(strategy_name: str):
    """注册分块器策略的装饰器"""

    def decorator(cls: Type["BaseChunker"]):
        _CHUNKER_REGISTRY[strategy_name] = cls
        return cls

    return decorator


class BaseChunker(ABC):
    """分块器抽象基类"""

    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def chunk(self, text: str) -> List[Dict[str, Any]]:
        """执行分块逻辑"""
        pass


@register_chunker(ChunkingStrategy.MARKDOWN_HIERARCHICAL.value)
class MarkdownHierarchicalChunker(BaseChunker):
    """基于Markdown标题层级的分块器"""

    def __init__(
        self,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 50,
        split_on_headers: bool = True,
        preserve_structure: bool = True,
        **kwargs,
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.split_on_headers = split_on_headers
        self.preserve_structure = preserve_structure

    def chunk(self, markdown: str) -> List[Dict[str, Any]]:
        """
        按照Markdown标题层级分块

        Args:
            markdown: Markdown文本内容

        Returns:
            分块列表，每个元素包含content和metadata
        """
        if not markdown or not markdown.strip():
            return []

        chunks = []
        current_chunk = ""
        current_header = ""
        chunk_index = 0

        # 按行处理
        lines = markdown.split("\n")

        for line in lines:
            # 检测标题行
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if header_match and self.split_on_headers:
                # 如果当前块有内容，保存它
                if current_chunk.strip():
                    if len(current_chunk) >= self.min_chunk_size:
                        chunks.append(
                            {
                                "content": current_chunk.strip(),
                                "index": chunk_index,
                                "type": "text",
                                "metadata": {
                                    "header": current_header,
                                    "char_count": len(current_chunk),
                                    "strategy": "markdown_hierarchical",
                                },
                            }
                        )
                        chunk_index += 1
                    current_chunk = ""

                # 开始新块
                current_header = header_match.group(2).strip()
                if self.preserve_structure:
                    current_chunk = line + "\n"
                else:
                    current_chunk = ""
            else:
                # 普通行，添加到当前块
                current_chunk += line + "\n"

                # 如果当前块超过最大大小，分割它
                if len(current_chunk) >= self.max_chunk_size:
                    chunks.append(
                        {
                            "content": current_chunk.strip(),
                            "index": chunk_index,
                            "type": "text",
                            "metadata": {
                                "header": current_header,
                                "char_count": len(current_chunk),
                                "strategy": "markdown_hierarchical",
                                "split_reason": "max_size_exceeded",
                            },
                        }
                    )
                    chunk_index += 1
                    current_chunk = ""

        # 保存最后一个块
        if current_chunk.strip() and len(current_chunk) >= self.min_chunk_size:
            chunks.append(
                {
                    "content": current_chunk.strip(),
                    "index": chunk_index,
                    "type": "text",
                    "metadata": {
                        "header": current_header,
                        "char_count": len(current_chunk),
                        "strategy": "markdown_hierarchical",
                    },
                }
            )

        return chunks


@register_chunker(ChunkingStrategy.FIXED_SIZE.value)
class FixedSizeChunker(BaseChunker):
    """固定大小分块器"""

    def __init__(self, max_chunk_size: int = 1000, overlap_size: int = 100, **kwargs):
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size

    def chunk(self, text: str) -> List[Dict[str, Any]]:
        """
        按固定大小分块，带重叠

        Args:
            text: 文本内容

        Returns:
            分块列表
        """
        if not text or not text.strip():
            return []

        chunks = []
        chunk_index = 0
        start = 0

        while start < len(text):
            # 计算结束位置
            end = min(start + self.max_chunk_size, len(text))

            # 提取块
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append(
                    {
                        "content": chunk_text.strip(),
                        "index": chunk_index,
                        "type": "text",
                        "metadata": {
                            "char_count": len(chunk_text),
                            "start_pos": start,
                            "end_pos": end,
                            "strategy": "fixed_size",
                        },
                    }
                )
                chunk_index += 1

            # 移动到下一个起始位置（带重叠）
            start = end - self.overlap_size if end < len(text) else end

        return chunks


@register_chunker(ChunkingStrategy.SEMANTIC.value)
class SemanticChunker(BaseChunker):
    """语义分块器（基于句子边界）"""

    def __init__(
        self,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 50,
        overlap_size: int = 100,
        **kwargs,
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size

        # 句子分割模式（支持中英文）
        self.sentence_pattern = re.compile(
            r"([^。！？.!?]+[。！？.!?]+|[^。！？.!?]+$)",
            re.UNICODE,
        )

    def chunk(self, text: str) -> List[Dict[str, Any]]:
        """
        按语义边界（句子）分块

        Args:
            text: 文本内容

        Returns:
            分块列表
        """
        if not text or not text.strip():
            return []

        # 分割成句子
        sentences = self.sentence_pattern.findall(text)
        if not sentences:
            # 如果没有匹配到句子，回退到固定大小分割
            return FixedSizeChunker(self.max_chunk_size, self.overlap_size).chunk(text)

        chunks = []
        chunk_index = 0
        current_chunk = ""
        sentence_buffer = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 如果添加当前句子会超过最大大小
            if len(current_chunk) + len(sentence) > self.max_chunk_size:
                # 保存当前块
                if current_chunk.strip() and len(current_chunk) >= self.min_chunk_size:
                    chunks.append(
                        {
                            "content": current_chunk.strip(),
                            "index": chunk_index,
                            "type": "text",
                            "metadata": {
                                "char_count": len(current_chunk),
                                "sentence_count": len(sentence_buffer),
                                "strategy": "semantic",
                            },
                        }
                    )
                    chunk_index += 1

                    # 保留重叠（最后几个句子）
                    overlap_text = ""
                    overlap_sentences = []
                    for s in reversed(sentence_buffer):
                        if len(overlap_text) + len(s) <= self.overlap_size:
                            overlap_sentences.insert(0, s)
                            overlap_text = " ".join(overlap_sentences)
                        else:
                            break

                    current_chunk = overlap_text + " " if overlap_text else ""
                    sentence_buffer = overlap_sentences.copy()

            # 添加当前句子
            current_chunk += sentence + " "
            sentence_buffer.append(sentence)

        # 保存最后一个块
        if current_chunk.strip() and len(current_chunk) >= self.min_chunk_size:
            chunks.append(
                {
                    "content": current_chunk.strip(),
                    "index": chunk_index,
                    "type": "text",
                    "metadata": {
                        "char_count": len(current_chunk),
                        "sentence_count": len(sentence_buffer),
                        "strategy": "semantic",
                    },
                }
            )

        return chunks


class ChunkingService:
    """分块服务主类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        logger.info("ChunkingService initialized")

    def chunk_markdown(
        self,
        markdown: str,
        strategy: str = "markdown_hierarchical",
        max_chunk_size: int = 1000,
        min_chunk_size: int = 50,
        overlap_size: int = 100,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        对Markdown文档进行分块

        Args:
            markdown: Markdown文本内容
            strategy: 分块策略
            max_chunk_size: 最大块大小（字符数）
            min_chunk_size: 最小块大小（字符数）
            overlap_size: 重叠大小（字符数）
            **kwargs: 其他策略特定参数

        Returns:
            分块列表，包含文本块和图片块
        """
        if not markdown or not markdown.strip():
            logger.warning("Empty markdown content provided for chunking")
            return []

        logger.info(
            f"Chunking markdown with strategy: {strategy}, "
            f"max_size: {max_chunk_size}, min_size: {min_chunk_size}"
        )

        # 首先提取图片引用
        image_chunks = self._extract_image_chunks(markdown)

        # 移除图片引用后的纯文本
        text_only = self._remove_image_references(markdown)

        # 根据策略选择分块器
        text_chunks = []

        chunker_cls = _CHUNKER_REGISTRY.get(strategy)

        if chunker_cls:
            # 实例化分块器，传入必要的参数
            # 使用 kwargs 将所有可能的参数透传给 __init__
            # 注意：每个 Chunk 的 __init__ 需要能处理多余参数 (通过 **kwargs)
            chunker = chunker_cls(
                max_chunk_size=max_chunk_size,
                min_chunk_size=min_chunk_size,
                overlap_size=overlap_size,
                **kwargs,
            )
            text_chunks = chunker.chunk(text_only)
        else:
            logger.warning(f"Unknown chunking strategy: {strategy}, using fixed size")
            # Fallback to FixedSize
            chunker = FixedSizeChunker(
                max_chunk_size=max_chunk_size, overlap_size=overlap_size, **kwargs
            )
            text_chunks = chunker.chunk(text_only)

        # 合并文本块和图片块
        print(type(text_chunks), type(image_chunks))
        all_chunks = text_chunks + image_chunks

        # 重新排序索引
        for idx, chunk in enumerate(all_chunks):
            chunk["index"] = idx

        logger.info(
            f"Chunking completed: {len(text_chunks)} text chunks, "
            f"{len(image_chunks)} image chunks, total: {len(all_chunks)}"
        )

        return all_chunks

    def _extract_image_chunks(self, markdown: str) -> List[Dict[str, Any]]:
        """
        从Markdown中提取图片引用

        Args:
            markdown: Markdown文本

        Returns:
            图片块列表
        """
        # 图片引用模式: ![alt text](image_path)
        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        image_chunks = []

        for idx, match in enumerate(re.finditer(pattern, markdown)):
            alt_text = match.group(1)
            image_path = match.group(2)

            # 从路径中提取文件名
            filename = image_path.split("/")[-1] if "/" in image_path else image_path

            image_chunks.append(
                {
                    "content": f"![{alt_text}]({image_path})",
                    "index": idx,  # 将在合并后重新编号
                    "type": "image",
                    "metadata": {
                        "alt_text": alt_text,
                        "image_path": image_path,
                        "filename": filename,
                        "strategy": "image_extraction",
                    },
                }
            )

        return image_chunks

    def _remove_image_references(self, markdown: str) -> str:
        """
        移除Markdown中的图片引用

        Args:
            markdown: Markdown文本

        Returns:
            移除图片引用后的文本
        """
        # 移除图片引用
        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        text_only = re.sub(pattern, "", markdown)

        # 清理多余的空行
        text_only = re.sub(r"\n{3,}", "\n\n", text_only)

        return text_only.strip()

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": "ChunkingService",
            "version": "1.0.0",
            "supported_strategies": [s.value for s in ChunkingStrategy],
            "default_max_chunk_size": 1000,
            "default_overlap_size": 100,
        }


# 默认分块服务实例
_default_chunking_service: Optional[ChunkingService] = None


def get_chunking_service(config: Optional[Dict[str, Any]] = None) -> ChunkingService:
    """获取默认分块服务实例（单例模式）"""
    global _default_chunking_service
    if _default_chunking_service is None:
        _default_chunking_service = ChunkingService(config=config)
    return _default_chunking_service
