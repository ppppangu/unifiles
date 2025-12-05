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


class SearchResult:
    """
    向量检索结果

    封装知识库检索返回的单个结果项
    """

    def __init__(self, result_data: Dict[str, Any]):
        """
        初始化检索结果

        Args:
            result_data: 服务端返回的结果数据字典
        """
        # 仅对外暴露统一组件ID；不暴露底层子表ID
        self.component_id: str = result_data.get("component_id", "")
        self.document_id: str = result_data.get("document_id", "")
        self.text_content: str = result_data.get("text_content", "")
        self.similarity_score: float = result_data.get("similarity_score", 0.0)

    def __repr__(self) -> str:
        """字符串表示"""
        preview = (
            self.text_content[:50] + "..."
            if len(self.text_content) > 50
            else self.text_content
        )
        return f"SearchResult(score={self.similarity_score:.3f}, text='{preview}')"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"[{self.similarity_score:.3f}] {self.text_content}"


class Document:
    """
    文档类 - 代表一个文档的完整生命周期

    支持三层处理：
    1. 文件存储层：原始文件
    2. 内容提取层：OCR处理后的内容（图片类/文字类）
    3. 知识库索引层：分块和向量化
    """

    def __init__(
        self, client: "Unifiles", file_id: str, file_info: Optional[Dict] = None
    ):
        self.client = client
        self.file_id = file_id
        self._file_info = file_info
        self._extracted_content = None
        self._indexed_content = None
        # 异步提取任务跟踪
        self._extraction_task_id: Optional[str] = None
        self._extraction_status: Optional[str] = (
            None  # queued|processing|completed|failed
        )

    @property
    def filename(self) -> str:
        """文件名"""
        if self._file_info:
            return self._file_info.get("filename", "")
        return self.get_info().get("filename", "")

    @property
    def status(self) -> DocumentStatus:
        """
        文档当前处理状态

        基于已缓存的数据推断文档状态：
        - INDEXED: 已索引到知识库
        - EXTRACTED: 已完成内容提取
        - UPLOADED: 仅上传完成
        """
        # 优先根据异步任务状态推断
        if self._extraction_status:
            st = self._extraction_status
            if st in {"queued", "processing", "pending"}:
                return DocumentStatus.EXTRACTING
            if st == "completed":
                return DocumentStatus.EXTRACTED
            if st in {"failed", "cancelled", "timeout"}:
                return DocumentStatus.FAILED

        if self._indexed_content:
            return DocumentStatus.INDEXED
        if self._extracted_content:
            return DocumentStatus.EXTRACTED
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

        Raises:
            UnifilesError: 如果内容未提取，需要先调用 extract_content()
        """
        if self._extracted_content is None:
            raise UnifilesError(
                f"Document content not extracted yet for {self.file_id}. "
                "Call extract_content() first to extract document content."
            )

        # 根据 content_type 过滤返回内容
        if content_type:
            if content_type == ContentType.TEXT:
                return {
                    "content": self._extracted_content.get("extracted_text", ""),
                    "type": "text",
                }
            if content_type == ContentType.IMAGE:
                return {
                    "content": self._extracted_content.get("markdown_content", ""),
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

        # 确保我们有任务ID可用
        def _ensure_task_id() -> Optional[str]:
            if self._extraction_task_id:
                return self._extraction_task_id
            try:
                tasks_resp = self.client._get(
                    "/tasks", params={"task_type": "extraction", "limit": 50}
                )
                for t in tasks_resp.get("tasks", []):
                    if t.get("entity_id") == self.file_id:
                        return t.get("task_id") or t.get("id")
            except Exception:
                return None
            return None

        task_id = _ensure_task_id()
        if not task_id:
            raise UnifilesError(
                "No extraction task found. Call extract_content() first."
            )

        try:
            while time.time() - start_time < timeout:
                try:
                    status_resp = self.client._get(f"/tasks/{task_id}")
                    st = (status_resp.get("status") or "").lower()
                    self._extraction_status = st

                    if st == "completed":
                        # 获取最终结果
                        result = self.client._get(f"/tasks/{task_id}/result")
                        extracted = result.get("extracted_content")
                        if extracted:
                            self._extracted_content = extracted
                        return True
                    if st in {"failed", "cancelled", "timeout"}:
                        raise UnifilesError(
                            f"Document extraction failed with status: {st}"
                        )

                    time.sleep(poll_interval)
                except UnifilesError as e:
                    msg = str(e).lower()
                    if "connection failed" in msg or "timeout" in msg:
                        time.sleep(poll_interval)
                    else:
                        raise

            raise UnifilesError(
                f"Document extraction timeout after {timeout} seconds for {self.file_id}"
            )
        except KeyboardInterrupt:
            raise UnifilesError("Document extraction cancelled by user")

    def extract_content(
        self,
        mode: str = "simple",
        *,
        parse_image_content: bool = False,
        wait: bool = False,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> Dict[str, Any]:
        """
        触发内容提取（第二层处理，异步任务）

        Args:
            mode: 提取模式 simple|mistral|selfhosted|openai
            parse_image_content: 是否解析图像内容到full_markdown (仅对支持的OCR提供商有效，如selfhosted)
            wait: 是否等待任务完成并返回内容
            timeout: 等待超时时间（秒），仅在 wait=True 时生效
            poll_interval: 轮询间隔（秒），仅在 wait=True 时生效

        Returns:
            - 当 wait=False 时：返回任务提交结果（task_id/status）
            - 当 wait=True 时：返回任务结果，包含 extracted_content

        Raises:
            ValueError: 当 parse_image_content=True 但 mode 不是 selfhosted 时
        """
        # 验证参数组合
        if parse_image_content and mode != "selfhosted":
            raise ValueError(
                f"parse_image_content 参数仅在 mode='selfhosted' 时有效，"
                f"当前 mode='{mode}'。"
                f"请使用 mode='selfhosted' 或设置 parse_image_content=False"
            )

        data = {
            "mode": mode,
            "parse_image_content": parse_image_content,
        }
        response = self.client._post(f"/files/{self.file_id}/extract", data=data)

        # 记录任务信息
        task_id = response.get("task_id")
        status = response.get("status")
        if task_id:
            self._extraction_task_id = task_id
            self._extraction_status = status or "queued"

        if wait and task_id:
            if self.wait_for_extraction(timeout=timeout, poll_interval=poll_interval):
                # 返回最终任务结果（包含 extracted_content）
                return self.client._get(f"/tasks/{task_id}/result")

        return response

    def index_to_knowledge_base(
        self, knowledge_base_id: str, chunk_strategy: str = "markdown_hierarchical"
    ) -> Dict[str, Any]:
        """
        将文档索引到知识库（第三层处理）

        Args:
            knowledge_base_id: 目标知识库ID
            chunk_strategy: 分块策略 markdown_hierarchical|fixed|semantic

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

    def __init__(self, client: "Unifiles", kb_id: str, kb_info: Optional[Dict] = None):
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
    def description(self) -> str:
        """知识库描述"""
        if self._kb_info:
            # 与服务端 KnowledgeBaseInfo 模型中的字段对齐
            return self._kb_info.get("description", "") or ""
        # 若本地没有信息，则返回空字符串避免属性缺失
        return ""

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
        extract_mode: str = "simple",
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
            # 第二层：内容提取（等待完成以便索引）
            document.extract_content(mode=extract_mode, wait=True)

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

    def search(
        self, query: str, top_k: int = 10, include_photos: bool = False
    ) -> List[SearchResult]:
        """
        在知识库中进行向量检索

        Args:
            query: 检索查询文本
            top_k: 返回结果数量，默认 10，范围 1-100
            include_photos: 是否在检索结果中包含图片组件（component_type='photo'），默认 False

        Returns:
            SearchResult 对象列表，按相似度降序排列

        Raises:
            UnifilesError: 检索失败时抛出
            ValueError: 参数验证失败时抛出

        Example:
            >>> kb = client.get_knowledge_base("kb_xxx")
            >>> results = kb.search("电气自动化设备", top_k=5)
            >>> for result in results:
            ...     print(f"相似度: {result.similarity_score:.3f}")
            ...     print(f"内容: {result.text_content}")
        """
        # 参数验证
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if top_k < 1 or top_k > 100:
            raise ValueError("top_k must be between 1 and 100")

        # 调用检索 API
        data = {"query": query, "top_k": top_k, "include_photos": include_photos}

        response = self.client._post(f"/knowledge-bases/{self.kb_id}/search", data=data)

        # 解析响应并构建 SearchResult 对象列表
        results = []
        for result_data in response.get("results", []):
            results.append(SearchResult(result_data))

        return results


class Unifiles:
    """
    Unifiles客户端 - 主入口点

    提供简洁的API来管理三层文档处理架构：
    1. 文件存储：上传、下载、管理原始文件
    2. 内容提取：OCR处理，获取文字类和图片类内容
    3. 知识库索引：文档分块、向量化和检索
    """

    def __init__(self, api_key: str, base_url: str = "http://localhost:8088"):
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
                raise AuthenticationError("Authentication failed: Invalid API key")
            if response.status_code == 403:
                raise UnifilesError("Access denied: Insufficient permissions")
            if response.status_code == 404:
                raise UnifilesError("Resource not found")
            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded: Too many requests")
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
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """POST请求"""
        if files:
            # 文件上传时需要让 requests 自动设置 Content-Type
            # 临时从 session 中移除 Content-Type，但保留 Authorization
            original_content_type = self.session.headers.pop("Content-Type", None)
            try:
                result = self._request(
                    "POST", endpoint, data=data, files=files, params=params
                )
                return result
            finally:
                # 恢复 Content-Type
                if original_content_type:
                    self.session.headers["Content-Type"] = original_content_type
        return self._request("POST", endpoint, json=data, params=params)

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

        # 文件类型检查（与服务端支持列表对齐）
        allowed_extensions = {
            # 文档类型
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".odt",
            ".ods",
            ".odp",
            ".txt",
            ".rtf",
            ".md",
            ".html",
            ".htm",
            ".csv",
            ".tsv",
            ".xml",
            # PDF
            ".pdf",
            # 图片类型
            ".jpg",
            ".jpeg",
            ".png",
            ".tiff",
            ".tif",
            ".bmp",
            # 代码类型
            ".py",
            ".ipynb",
            ".js",
            ".json",
        }
        if file_path.suffix.lower() not in allowed_extensions:
            raise UnifilesError(f"Unsupported file type: {file_path.suffix}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                # is_public 作为查询参数，需要小写字符串 "true" 或 "false"
                # Python 的 requests 会将 False 转换为 "False"（大写），FastAPI 无法识别
                params = {"is_public": "true" if is_public else "false"}

                response = self._post("/files", files=files, params=params)

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

        Raises:
            UnifilesError: 创建失败时抛出
        """
        data = {"name": name, "description": description}
        response = self._post("/knowledge-bases", data=data)
        kb_info = response.get("knowledge_base", {})
        kb_id = kb_info.get("kb_id")

        if not kb_id:
            raise UnifilesError("Server did not return kb_id after creation")

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
        self,
        file_path: Union[str, Path],
        knowledge_base_name: Optional[str] = None,
        extract_mode: str = "simple",
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

        # 触发内容提取并等待完成
        document.extract_content(mode=extract_mode, wait=True)

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
