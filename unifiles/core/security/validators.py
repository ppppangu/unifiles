import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class FileSecurityValidator:
    """文件安全验证器，用于验证上传文件的安全性"""

    # 文件魔数验证映射
    MAGIC_NUMBERS = {
        # Images
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"\xff\xd8\xff": "image/jpeg",
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
        b"BM": "image/bmp",
        b"RIFF": "image/webp",  # Note: WebP also uses RIFF
        b"II*\x00": "image/tiff",
        b"MM\x00*": "image/tiff",
        # Documents
        b"%PDF": "application/pdf",
        b"PK\x03\x04": "application/zip",  # Also covers docx, xlsx, pptx
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "application/msoffice",  # Old Office formats
        # Text
        b"\xef\xbb\xbf": "text/utf8-bom",  # UTF-8 BOM
        # Archives
        b"Rar!\x1a\x07\x00": "application/x-rar-compressed",
        b"\x1f\x8b\x08": "application/gzip",
        b"7z\xbc\xaf\x27\x1c": "application/x-7z-compressed",
    }

    # 允许的文件扩展名和对应的MIME类型
    ALLOWED_EXTENSIONS = {
        # 文档类型
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".odt": "application/vnd.oasis.opendocument.text",
        ".ods": "application/vnd.oasis.opendocument.spreadsheet",
        ".odp": "application/vnd.oasis.opendocument.presentation",
        ".txt": "text/plain",
        ".rtf": "application/rtf",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".xml": "application/xml",
        ".html": "text/html",
        ".htm": "text/html",
        # 图片类型
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        # 代码类型
        ".py": "text/x-python",
        ".js": "application/javascript",
        ".json": "application/json",
        ".ipynb": "application/x-ipynb+json",
    }

    # 危险文件扩展名黑名单
    DANGEROUS_EXTENSIONS = {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scr",
        ".vbs",
        ".vbe",
        ".js",
        ".jar",
        ".wsf",
        ".wsh",
        ".ps1",
        ".sh",
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".war",
        ".ear",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
    }

    # 最大文件大小限制 (bytes)
    MAX_FILE_SIZES = {
        "image/*": 10 * 1024 * 1024,  # 10MB for images
        "application/pdf": 50 * 1024 * 1024,  # 50MB for PDFs
        "text/*": 1 * 1024 * 1024,  # 1MB for text files
        "application/*": 100 * 1024 * 1024,  # 100MB for other applications
        "default": 50 * 1024 * 1024,  # 50MB default
    }

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，防止路径遍历和其他安全问题

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名
        """
        if not filename:
            return "unnamed_file"

        # 移除路径分隔符和危险字符
        safe_filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

        # 移除开头的点号（隐藏文件）
        safe_filename = re.sub(r"^\.+", "", safe_filename)

        # 限制长度
        name_part, ext_part = Path(safe_filename).stem, Path(safe_filename).suffix
        if len(name_part) > 200:
            name_part = name_part[:200]

        # 确保有文件名
        if not name_part:
            name_part = "file"

        return f"{name_part}{ext_part.lower()}"

    @staticmethod
    def validate_file_extension(filename: str) -> Tuple[bool, str]:
        """
        验证文件扩展名是否允许

        Args:
            filename: 文件名

        Returns:
            (是否允许, 错误信息或空字符串)
        """
        ext = Path(filename).suffix.lower()

        if not ext:
            return False, "File must have an extension"

        if ext in FileSecurityValidator.DANGEROUS_EXTENSIONS:
            return False, f"File extension '{ext}' is not allowed for security reasons"

        if ext not in FileSecurityValidator.ALLOWED_EXTENSIONS:
            return False, f"File extension '{ext}' is not supported"

        return True, ""

    @staticmethod
    def validate_file_content(
        content: bytes, filename: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        验证文件内容与扩展名是否匹配

        Args:
            content: 文件内容
            filename: 文件名

        Returns:
            (是否有效, 错误信息, 检测到的MIME类型)
        """
        if len(content) == 0:
            return False, "Empty file not allowed", None

        # 检测文件魔数
        detected_mime = FileSecurityValidator._detect_mime_from_content(content)
        expected_mime = FileSecurityValidator.ALLOWED_EXTENSIONS.get(
            Path(filename).suffix.lower()
        )

        # 特殊处理：Office文档都用ZIP格式
        if (
            expected_mime
            and "officedocument" in expected_mime
            and detected_mime == "application/zip"
        ):
            detected_mime = expected_mime

        # 特殊处理：文本文件
        if expected_mime and expected_mime.startswith("text/"):
            if FileSecurityValidator._is_text_content(content):
                detected_mime = expected_mime

        # 验证MIME类型是否匹配
        if detected_mime and expected_mime:
            # 主类型匹配检查
            detected_main = detected_mime.split("/")[0]
            expected_main = expected_mime.split("/")[0]

            if detected_main != expected_main and detected_mime != expected_mime:
                return (
                    False,
                    f"File content ({detected_mime}) doesn't match extension ({expected_mime})",
                    detected_mime,
                )

        return True, "", detected_mime or expected_mime

    @staticmethod
    def validate_file_size(content: bytes, content_type: str) -> Tuple[bool, str]:
        """
        验证文件大小是否在允许范围内

        Args:
            content: 文件内容
            content_type: MIME类型

        Returns:
            (是否允许, 错误信息)
        """
        file_size = len(content)

        # 查找对应的大小限制
        max_size = FileSecurityValidator.MAX_FILE_SIZES.get("default")

        for pattern, size_limit in FileSecurityValidator.MAX_FILE_SIZES.items():
            if pattern != "default" and content_type.startswith(
                pattern.replace("*", "")
            ):
                max_size = size_limit
                break

        if file_size > max_size:
            return (
                False,
                f"File size ({file_size} bytes) exceeds limit ({max_size} bytes)",
            )

        return True, ""

    @staticmethod
    def _detect_mime_from_content(content: bytes) -> Optional[str]:
        """根据文件内容检测MIME类型"""
        for magic_bytes, mime_type in FileSecurityValidator.MAGIC_NUMBERS.items():
            if content.startswith(magic_bytes):
                return mime_type

        # 尝试检测是否为文本内容
        if FileSecurityValidator._is_text_content(content):
            return "text/plain"

        return None

    @staticmethod
    def _is_text_content(content: bytes, sample_size: int = 1024) -> bool:
        """检测内容是否为文本"""
        try:
            # 取样检查
            sample = content[:sample_size]
            sample.decode("utf-8")

            # 检查是否包含过多的控制字符
            control_chars = sum(
                1 for byte in sample if byte < 32 and byte not in [9, 10, 13]
            )
            control_ratio = control_chars / len(sample) if sample else 0

            return control_ratio < 0.1  # 控制字符比例小于10%
        except UnicodeDecodeError:
            return False

    @staticmethod
    def generate_secure_path(user_id: str, file_id: str, filename: str) -> str:
        """
        生成安全的文件存储路径

        Args:
            user_id: 用户ID
            file_id: 文件ID
            filename: 文件名

        Returns:
            安全的存储路径
        """
        # 清理输入
        safe_user_id = re.sub(r"[^a-zA-Z0-9\-_]", "_", user_id)
        safe_file_id = re.sub(r"[^a-zA-Z0-9\-_]", "_", file_id)
        safe_filename = FileSecurityValidator.sanitize_filename(filename)

        # 添加日期分片来避免单个目录文件过多
        from datetime import datetime

        date_prefix = datetime.now().strftime("%Y/%m")

        return f"{safe_user_id}/{date_prefix}/{safe_file_id}/{safe_filename}"

    @classmethod
    def validate_upload_file(cls, content: bytes, filename: str) -> Dict[str, Any]:
        """
        综合验证上传文件

        Args:
            content: 文件内容
            filename: 文件名

        Returns:
            验证结果字典
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "sanitized_filename": "",
            "detected_mime_type": None,
            "file_size": len(content),
        }

        # 1. 清理文件名
        result["sanitized_filename"] = cls.sanitize_filename(filename)

        # 2. 验证文件扩展名
        ext_valid, ext_error = cls.validate_file_extension(result["sanitized_filename"])
        if not ext_valid:
            result["valid"] = False
            result["errors"].append(ext_error)
            return result

        # 3. 验证文件内容
        content_valid, content_error, detected_mime = cls.validate_file_content(
            content, result["sanitized_filename"]
        )
        result["detected_mime_type"] = detected_mime

        if not content_valid:
            result["valid"] = False
            result["errors"].append(content_error)

        # 4. 验证文件大小
        if detected_mime:
            size_valid, size_error = cls.validate_file_size(content, detected_mime)
            if not size_valid:
                result["valid"] = False
                result["errors"].append(size_error)

        # Debug logging
        import sys
        print(f"DEBUG VALIDATOR: About to return result", file=sys.stderr)
        print(f"DEBUG VALIDATOR: result type = {type(result)}", file=sys.stderr)
        print(f"DEBUG VALIDATOR: result = {result}", file=sys.stderr)
        sys.stderr.flush()

        return result


class PathSecurityValidator:
    """路径安全验证器"""

    @staticmethod
    def validate_object_path(object_path: str) -> Tuple[bool, str]:
        """
        验证对象路径是否安全

        Args:
            object_path: 对象路径

        Returns:
            (是否安全, 错误信息)
        """
        if not object_path:
            return False, "Empty path not allowed"

        # 检查路径遍历
        if ".." in object_path or object_path.startswith("/"):
            return False, "Path traversal detected"

        # 检查危险字符
        if re.search(r'[<>:"|?*\x00-\x1f]', object_path):
            return False, "Invalid characters in path"

        # 检查路径长度
        if len(object_path) > 1024:
            return False, "Path too long"

        return True, ""


# 权限验证装饰器
from functools import wraps

from fastapi import HTTPException, Request


def require_file_ownership(func):
    """装饰器：要求文件归属验证"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 从参数中提取request和file_id
        request = None
        file_id = None

        for arg in args:
            if isinstance(arg, Request):
                request = arg
            elif isinstance(arg, str) and arg.startswith("file-"):
                file_id = arg

        if "request" in kwargs:
            request = kwargs["request"]
        if "file_id" in kwargs:
            file_id = kwargs["file_id"]

        if not request or not file_id:
            raise HTTPException(status_code=400, detail="Missing request or file_id")

        # 验证文件所有权
        from unifiles.core.database import file_db_manager

        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        if file_record.get("user_id") != request.state.user_id:
            raise HTTPException(
                status_code=403, detail="Access denied: file belongs to another user"
            )

        return await func(*args, **kwargs)

    return wrapper


# ==== 文件工具函数 (从 utils/file_utils.py 迁移) ====


class FileUtils:
    """文件处理工具类，整合文件相关的通用功能"""

    @staticmethod
    def detect_content_type(
        file_name: str, default: str = "application/octet-stream"
    ) -> str:
        """
        根据文件扩展名智能检测 Content-Type

        Args:
            file_name: 文件名或路径, 用于提取扩展名
            default: 无法识别时返回的默认 Content-Type

        Returns:
            合适的 MIME 类型字符串, 失败时返回 default
        """
        # 先使用标准库猜测
        mime_type, _ = mimetypes.guess_type(file_name)
        if mime_type:
            return mime_type

        # 扩展自定义映射
        ext = Path(file_name).suffix.lower()

        custom_mapping = {
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".yml": "application/x-yaml",
            ".yaml": "application/x-yaml",
            ".log": "text/plain",
            ".conf": "text/plain",
            ".cfg": "text/plain",
            ".ini": "text/plain",
        }

        return custom_mapping.get(ext, default)

    @staticmethod
    def get_file_category(file_name: str) -> str:
        """
        根据文件名获取文件分类

        Args:
            file_name: 文件名

        Returns:
            文件分类: document, image, code, archive, etc.
        """
        ext = Path(file_name).suffix.lower()

        document_exts = {
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".odt",
            ".ods",
            ".odp",
            ".txt",
            ".rtf",
            ".md",
        }
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
        code_exts = {".py", ".js", ".html", ".css", ".json", ".xml", ".yml", ".yaml"}
        archive_exts = {".zip", ".tar", ".gz", ".rar", ".7z"}

        if ext in document_exts:
            return "document"
        if ext in image_exts:
            return "image"
        if ext in code_exts:
            return "code"
        if ext in archive_exts:
            return "archive"
        return "unknown"

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        格式化文件大小为人类可读格式

        Args:
            size_bytes: 文件大小（字节）

        Returns:
            格式化的文件大小字符串
        """
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """
        检查文件名是否安全（不包含危险字符）

        Args:
            filename: 文件名

        Returns:
            是否安全
        """
        dangerous_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
        return not any(char in filename for char in dangerous_chars)

    @staticmethod
    def extract_file_extension(filename: str) -> str:
        """
        提取文件扩展名

        Args:
            filename: 文件名

        Returns:
            文件扩展名（包含点号）
        """
        return Path(filename).suffix.lower()
