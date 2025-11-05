"""
文档处理器工厂

统一管理各种文档处理器的创建和调用
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from .base import BaseDocumentProcessor, DocumentProcessor


class ProcessingFactory:
    """处理器工厂类"""

    def __init__(self):
        self._processors: Dict[str, type] = {}
        self._instances: Dict[str, DocumentProcessor] = {}
        self._register_default_processors()

    def _register_default_processors(self):
        """注册默认处理器"""
        self.register_processor("base", BaseDocumentProcessor)

        # 尝试注册其他处理器
        try:
            from .document import DocumentProcessor as DocProcessor

            self.register_processor("document", DocProcessor)
        except ImportError:
            logger.debug("Document processor not available")

        try:
            from .pdf import PDFProcessor

            self.register_processor("pdf", PDFProcessor)
        except ImportError:
            logger.debug("PDF processor not available")

        try:
            from .ocr import OCRProcessor

            self.register_processor("ocr", OCRProcessor)
        except ImportError:
            logger.debug("OCR processor not available")

    def register_processor(self, name: str, processor_class: type):
        """
        注册处理器

        Args:
            name: 处理器名称
            processor_class: 处理器类
        """
        if not issubclass(processor_class, DocumentProcessor):
            raise ValueError("Processor class must inherit from DocumentProcessor")

        self._processors[name] = processor_class
        logger.info(f"Registered processor: {name}")

    def get_processor(self, file_type: str) -> Optional[DocumentProcessor]:
        """
        根据文件类型获取处理器

        Args:
            file_type: MIME类型

        Returns:
            处理器实例
        """
        processor_name = self._get_processor_name_for_type(file_type)

        if processor_name not in self._processors:
            processor_name = "base"  # 回退到基础处理器

        # 获取或创建处理器实例
        if processor_name not in self._instances:
            processor_class = self._processors[processor_name]
            self._instances[processor_name] = processor_class()

        return self._instances[processor_name]

    def _get_processor_name_for_type(self, file_type: str) -> str:
        """根据文件类型确定处理器名称"""
        if file_type.startswith("image/"):
            return "ocr"
        if file_type == "application/pdf":
            return "pdf"
        if file_type.startswith("text/") or "document" in file_type:
            return "document"
        return "base"

    def get_available_processors(self) -> List[str]:
        """获取可用的处理器列表"""
        return list(self._processors.keys())

    def get_processor_info(self, name: str) -> Dict[str, Any]:
        """
        获取处理器信息

        Args:
            name: 处理器名称

        Returns:
            处理器信息
        """
        if name not in self._processors:
            return {}

        processor_class = self._processors[name]

        # 尝试获取实例来获取更多信息
        try:
            if name not in self._instances:
                self._instances[name] = processor_class()

            instance = self._instances[name]

            return {
                "name": name,
                "class": processor_class.__name__,
                "supported_types": instance.get_supported_types(),
                "processor_name": instance.get_processor_name(),
            }
        except Exception as e:
            logger.warning(f"Failed to get info for processor {name}: {e}")
            return {"name": name, "class": processor_class.__name__, "error": str(e)}

    def list_processors_info(self) -> List[Dict[str, Any]]:
        """列出所有处理器信息"""
        return [self.get_processor_info(name) for name in self._processors]


# 全局工厂实例
processing_factory = ProcessingFactory()
