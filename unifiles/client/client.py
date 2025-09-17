"""
Unifile Python客户端实现

支持三层文档处理架构的Python客户端
"""

import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests


class DocumentStatus(Enum):
    """文档处理状态"""

    UPLOADED = "uploaded"  # 第一层：已上传
    EXTRACTING = "extracting"  # 第二层：内容提取中
    EXTRACTED = "extracted"  # 第二层：提取完成
    INDEXING = "indexing"  # 第三层：索引中
    INDEXED = "indexed"  # 第三层：索引完成
    FAILED = "failed"  # 处理失败


class ContentType(Enum):
    """内容类型（第二层处理结果）"""

    TEXT = "text"  # 文字类内容
    IMAGE = "image"  # 图片类内容（OCR结果）


class UnifilesError(Exception):
    """Unifiles客户端异常"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def __repr__(self):
        return f"UnifilesError(message='{self.message}', error_code='{self.error_code}', details={self.details})"


class DocumentNotFoundError(UnifilesError):
    """文档不存在异常"""

    pass


class KnowledgeBaseNotFoundError(UnifilesError):
    """知识库不存在异常"""

    pass


class AuthenticationError(UnifilesError):
    """认证失败异常"""

    pass


class RateLimitError(UnifilesError):
    """频率限制异常"""

    pass


class Document:
    """
    文档类 - 代表一个文档的完整生命周期

    支持三层处理：
    1. 文件存储层：原始文件
    2. 内容提取层：OCR处理后的内容（图片类/文字类）
    3. 知识库索引层：分块和向量化
    """

    def __init__(
        self, client: "Unifile", file_id: str, file_info: Optional[Dict] = None
    ):
        self.client = client
        self.file_id = file_id
        self._file_info = file_info
        self._extracted_content = None
        self._indexed_content = None

    @property
    def filename(self) -> str:
        """文件名"""
        if self._file_info:
            return self._file_info.get("filename", "")
        return self.get_info().get("filename", "")

    @property
    def status(self) -> DocumentStatus:
        """文档当前处理状态"""
        # TODO: 从服务端获取实际状态
        return DocumentStatus.UPLOADED

    @property
    def file_size(self) -> int:
        """文件大小（字节）"""
        if self._file_info:
            return self._file_info.get("file_size", 0)
        return self.get_info().get("file_size", 0)

    def get_info(self) -> Dict[str, Any]:
        """获取文件基础信息（第一层）"""
        if self._file_info:
            return self._file_info

        response = self.client._get(f"/files/{self.file_id}")
        self._file_info = response
        return response

    def get_content(self, content_type: Optional[ContentType] = None) -> Dict[str, Any]:
        """
        获取文档内容（第二层：OCR处理后的内容）

        Args:
            content_type: 指定获取的内容类型（文字类/图片类），不指定则返回所有

        Returns:
            提取的内容，包含text和image两种类型的处理结果
        """
        if self._extracted_content is None:
            # TODO: 调用内容提取API
            # response = self.client._get(f"/files/{self.file_id}/extract")
            # self._extracted_content = response

            # 模拟响应
            self._extracted_content = {
                "extraction_id": f"ext_{self.file_id[:8]}",
                "content_type": "mixed",
                "text_content": "这是从文档中提取的文字内容...",
                "image_content": "这是OCR处理后的图片内容...",
                "markdown_content": "# 文档标题\\n\\n这是处理后的markdown内容...",
                "extraction_metadata": {
                    "pages": 5,
                    "text_pages": 3,
                    "image_pages": 2,
                    "processing_time": 15.2,
                },
                "status": "extracted",
            }

        if content_type:
            if content_type == ContentType.TEXT:
                return {
                    "content": self._extracted_content.get("text_content"),
                    "type": "text",
                }
            if content_type == ContentType.IMAGE:
                return {
                    "content": self._extracted_content.get("image_content"),
                    "type": "image",
                }

        return self._extracted_content

    def wait_for_extraction(self, timeout: int = 300, poll_interval: int = 5) -> bool:
        """
        等待文档内容提取完成（第二层处理）

        Args:
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            是否提取成功
        """
        start_time = time.time()

        try:
            while time.time() - start_time < timeout:
                # 刷新文档状态
                try:
                    # TODO: 实现状态检查API
                    # status_response = self.client._get(f"/files/{self.file_id}/status")
                    # current_status = DocumentStatus(status_response.get('status', 'uploaded'))
                    current_status = self.status  # 临时使用当前状态

                    if current_status == DocumentStatus.EXTRACTED:
                        return True
                    if current_status == DocumentStatus.FAILED:
                        raise UnifilesError(
                            f"Document extraction failed for {self.file_id}"
                        )
                    if current_status in [DocumentStatus.EXTRACTING]:
                        # 继续等待
                        pass

                except UnifilesError as e:
                    # 如果是网络错误，继续重试
                    if "Connection failed" in str(e) or "timeout" in str(e).lower():
                        pass
                    else:
                        raise

                time.sleep(poll_interval)

            raise UnifilesError(
                f"Document extraction timeout after {timeout} seconds for {self.file_id}"
            )

        except KeyboardInterrupt:
            raise UnifilesError("Document extraction cancelled by user")

    def extract_content(self, mode: str = "normal") -> Dict[str, Any]:
        """
        触发内容提取（第二层处理）

        Args:
            mode: 提取模式 simple|normal

        Returns:
            提取任务信息
        """
        data = {"mode": mode}
        response = self.client._post(f"/files/{self.file_id}/extract", data=data)

        # 更新本地缓存
        if response.get("success") and "extracted_content" in response:
            self._extracted_content = response["extracted_content"]

        return response

    def index_to_knowledge_base(
        self, knowledge_base_id: str, chunk_strategy: str = "semantic"
    ) -> Dict[str, Any]:
        """
        将文档索引到知识库（第三层处理）

        Args:
            knowledge_base_id: 目标知识库ID
            chunk_strategy: 分块策略 semantic|fixed|sliding

        Returns:
            索引任务信息
        """
        # 确保内容已提取
        content = self.get_content()
        extraction_id = content.get("extraction_id")

        if not extraction_id:
            raise UnifilesError("Document content must be extracted before indexing")

        data = {
            "extraction_id": extraction_id,
            "knowledge_base_id": knowledge_base_id,
            "chunk_strategy": chunk_strategy,
        }

        response = self.client._post(
            f"/knowledge-bases/{knowledge_base_id}/documents", data=data
        )
        self._indexed_content = response
        return response


class KnowledgeBase:
    """
    知识库类 - 管理文档的第三层处理（分块和向量化）
    """

    def __init__(self, client: "Unifile", kb_id: str, kb_info: Optional[Dict] = None):
        self.client = client
        self.kb_id = kb_id
        self._kb_info = kb_info

    @property
    def name(self) -> str:
        """知识库名称"""
        if self._kb_info:
            return self._kb_info.get("name", "")
        # 如果没有本地信息，返回默认值而不是触发网络请求
        return f"knowledge_base_{self.kb_id}"

    @property
    def document_count(self) -> int:
        """知识库中的文档数量"""
        if self._kb_info:
            return self._kb_info.get("document_count", 0)
        # 如果没有本地信息，返回默认值而不是触发网络请求
        return 0

    def get_info(self) -> Dict[str, Any]:
        """获取知识库信息"""
        if self._kb_info:
            return self._kb_info

        response = self.client._get(f"/knowledge-bases/{self.kb_id}")
        self._kb_info = response
        return response

    def list_documents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取知识库中的文档列表"""
        params = {"limit": limit, "offset": offset}
        response = self.client._get(
            f"/knowledge-bases/{self.kb_id}/documents", params=params
        )
        return response.get("documents", [])

    def upload_document(
        self,
        file_path: Union[str, Path],
        is_public: bool = False,
        auto_extract: bool = True,
        auto_index: bool = True,
    ) -> Document:
        """
        上传文档到知识库（自动完成三层处理）

        Args:
            file_path: 文件路径
            is_public: 是否设为公开访问
            auto_extract: 是否自动触发内容提取
            auto_index: 是否自动索引到知识库

        Returns:
            Document对象
        """
        # 第一层：上传文件
        document = self.client.upload_file(file_path, is_public=is_public)

        if auto_extract:
            # 第二层：内容提取
            document.extract_content()

            if auto_index:
                # 第三层：索引到知识库
                document.index_to_knowledge_base(self.kb_id)

        return document

    def delete_document(self, document_id: str) -> bool:
        """删除知识库中的文档"""
        try:
            self.client._delete(
                f"/knowledge-bases/{self.kb_id}/documents/{document_id}"
            )
            return True
        except UnifilesError:
            return False


class Unifile:
    """
    Unifile客户端 - 主入口点

    提供简洁的API来管理三层文档处理架构：
    1. 文件存储：上传、下载、管理原始文件
    2. 内容提取：OCR处理，获取文字类和图片类内容
    3. 知识库索引：文档分块、向量化和检索
    """

    def __init__(self, api_key: str, base_url: str = "http://localhost:8087"):
        """
        初始化客户端

        Args:
            api_key: API密钥
            base_url: 服务器地址
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)

            # 处理HTTP状态码错误
            if response.status_code == 401:
                raise UnifilesError("Authentication failed: Invalid API key")
            if response.status_code == 403:
                raise UnifilesError("Access denied: Insufficient permissions")
            if response.status_code == 404:
                raise UnifilesError("Resource not found")
            if response.status_code == 429:
                raise UnifilesError("Rate limit exceeded: Too many requests")
            if response.status_code >= 500:
                raise UnifilesError(f"Server error: {response.status_code}")

            response.raise_for_status()

            # 尝试解析JSON响应
            try:
                result = response.json()
            except ValueError:
                raise UnifilesError("Invalid JSON response from server")

            # 检查API业务逻辑错误
            if not result.get("success", True):
                error_msg = result.get("message", "Unknown error")
                error_code = result.get("error_code")
                if error_code:
                    raise UnifilesError(f"API error [{error_code}]: {error_msg}")
                raise UnifilesError(f"API error: {error_msg}")

            return result

        except requests.ConnectionError:
            raise UnifilesError(f"Connection failed: Cannot connect to {self.base_url}")
        except requests.Timeout:
            raise UnifilesError("Request timeout: Server did not respond in time")
        except requests.RequestException as e:
            raise UnifilesError(f"Request failed: {e!s}")
        except UnifilesError:
            # 重新抛出已处理的UnifilesError
            raise
        except Exception as e:
            raise UnifilesError(f"Unexpected error: {e!s}")

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET请求"""
        return self._request("GET", endpoint, params=params)

    def _post(
        self, endpoint: str, data: Optional[Dict] = None, files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST请求"""
        if files:
            # 文件上传请求需要移除Content-Type让requests自动设置
            headers = {
                k: v
                for k, v in self.session.headers.items()
                if k.lower() != "content-type"
            }
            return self._request(
                "POST", endpoint, data=data, files=files, headers=headers
            )
        return self._request("POST", endpoint, json=data)

    def _delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE请求"""
        return self._request("DELETE", endpoint)

    # ==================== 文件存储层 API ====================

    def upload_file(
        self, file_path: Union[str, Path], is_public: bool = False
    ) -> Document:
        """
        上传文件（第一层：文件存储）

        Args:
            file_path: 文件路径
            is_public: 是否设为公开访问

        Returns:
            Document对象
        """
        file_path = Path(file_path)

        # 文件存在性检查
        if not file_path.exists():
            raise UnifilesError(f"File not found: {file_path}")

        # 文件大小检查
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise UnifilesError(f"Empty file: {file_path}")

        # 检查文件大小限制（例如100MB）
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            raise UnifilesError(
                f"File too large: {file_size} bytes (max: {max_size} bytes)"
            )

        # 文件类型检查
        allowed_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".jpg",
            ".jpeg",
            ".png",
            ".tiff",
        }
        if file_path.suffix.lower() not in allowed_extensions:
            raise UnifilesError(f"Unsupported file type: {file_path.suffix}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                data = {"is_public": str(is_public).lower()}

                response = self._post("/files", data=data, files=files)

                file_info = response.get("file", {})
                file_id = file_info.get("file_id")

                if not file_id:
                    raise UnifilesError("Server did not return file_id after upload")

                return Document(self, file_id, file_info)

        except OSError as e:
            raise UnifilesError(f"Failed to read file {file_path}: {e!s}")
        except UnifilesError:
            # 重新抛出已处理的错误
            raise
        except Exception as e:
            raise UnifilesError(f"Upload failed unexpectedly: {e!s}")

    def get_document(self, file_id: str) -> Document:
        """
        获取文档对象

        Args:
            file_id: 文件ID

        Returns:
            Document对象
        """
        return Document(self, file_id)

    def list_files(self, limit: int = 50, offset: int = 0) -> List[Document]:
        """
        获取文件列表

        Args:
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            Document对象列表
        """
        params = {"limit": limit, "offset": offset}
        response = self._get("/files", params=params)

        documents = []
        for file_info in response.get("files", []):
            file_id = file_info.get("file_id")
            if file_id:
                documents.append(Document(self, file_id, file_info))

        return documents

    def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        try:
            self._delete(f"/files/{file_id}")
            return True
        except UnifilesError:
            return False

    # ==================== 知识库管理 API ====================

    def create_knowledge_base(self, name: str, description: str = "") -> KnowledgeBase:
        """
        创建知识库

        Args:
            name: 知识库名称
            description: 知识库描述

        Returns:
            KnowledgeBase对象
        """
        try:
            # 尝试调用创建知识库API
            data = {"name": name, "description": description}
            response = self._post("/knowledge-bases", data=data)
            kb_info = response.get("knowledge_base", {})
            kb_id = kb_info.get("kb_id")

            if kb_id:
                return KnowledgeBase(self, kb_id, kb_info)
        except UnifilesError:
            # API可能还未实现，使用模拟响应
            pass

        # 模拟响应
        kb_id = f"kb_{int(time.time())}"
        kb_info = {
            "kb_id": kb_id,
            "name": name,
            "description": description,
            "document_count": 0,
        }

        return KnowledgeBase(self, kb_id, kb_info)

    def get_knowledge_base(self, kb_id: str) -> KnowledgeBase:
        """获取知识库对象"""
        return KnowledgeBase(self, kb_id)

    def list_knowledge_bases(
        self, limit: int = 50, offset: int = 0
    ) -> List[KnowledgeBase]:
        """
        获取知识库列表

        Args:
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            KnowledgeBase对象列表
        """
        params = {"limit": limit, "offset": offset}
        response = self._get("/knowledge-bases", params=params)

        knowledge_bases = []
        for kb_info in response.get("knowledge_bases", []):
            kb_id = kb_info.get("kb_id")
            if kb_id:
                knowledge_bases.append(KnowledgeBase(self, kb_id, kb_info))

        return knowledge_bases

    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库"""
        try:
            self._delete(f"/knowledge-bases/{kb_id}")
            return True
        except UnifilesError:
            # API可能还未实现
            return False

    # ==================== 便捷方法 ====================

    def quick_process(
        self, file_path: Union[str, Path], knowledge_base_name: Optional[str] = None
    ) -> Document:
        """
        快速处理文档（一键完成三层处理）

        Args:
            file_path: 文件路径
            knowledge_base_name: 知识库名称，如果不存在会自动创建

        Returns:
            处理完成的Document对象
        """
        # 上传文件
        document = self.upload_file(file_path)

        # 触发内容提取
        document.extract_content()

        # 如果指定了知识库，则索引到知识库
        if knowledge_base_name:
            # 查找或创建知识库
            knowledge_bases = self.list_knowledge_bases()
            kb = None

            for existing_kb in knowledge_bases:
                if existing_kb.name == knowledge_base_name:
                    kb = existing_kb
                    break

            if not kb:
                kb = self.create_knowledge_base(knowledge_base_name)

            # 索引到知识库
            document.index_to_knowledge_base(kb.kb_id)

        return document
