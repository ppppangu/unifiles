"""
文件处理工具函数

包含文件类型检测、验证等通用功能
"""

import mimetypes
from pathlib import Path


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


def extract_file_extension(filename: str) -> str:
    """
    提取文件扩展名

    Args:
        filename: 文件名

    Returns:
        文件扩展名（包含点号）
    """
    return Path(filename).suffix.lower()
