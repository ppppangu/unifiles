"""
数据库模块公共辅助函数
提供 JSON 解析、类型转换等通用功能
"""

import json
from typing import Any, List, Optional


def parse_json_field(value: Any, default: Optional[Any] = None) -> Any:
    """
    安全解析 JSON 字段

    Args:
        value: 待解析的值（可以是 dict、list、str 或 None）
        default: 解析失败时的默认值

    Returns:
        解析后的值
    """
    if value is None:
        return default if default is not None else {}

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default if default is not None else {}

    return default if default is not None else {}


def parse_string_list(value: Any) -> List[str]:
    """
    安全解析字符串列表字段（如 document_ids, tags 等）

    Args:
        value: 待解析的值

    Returns:
        字符串列表
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    # Fallback: 尝试转换为 list
    try:
        return list(value)
    except (TypeError, ValueError):
        return []


def to_json_string(value: Any) -> str:
    """
    将值转换为 JSON 字符串，用于数据库存储

    Args:
        value: 待转换的值

    Returns:
        JSON 字符串
    """
    if value is None:
        return "{}"

    if isinstance(value, str):
        # 验证是否已经是有效的 JSON 字符串
        try:
            json.loads(value)
            return value
        except (json.JSONDecodeError, ValueError):
            return json.dumps(value)

    return json.dumps(value)


def parse_db_result_count(result: Optional[str]) -> int:
    """
    从数据库执行结果中解析影响的行数

    Args:
        result: 数据库执行返回的结果字符串（如 "UPDATE 1", "DELETE 5"）

    Returns:
        影响的行数
    """
    if not result:
        return 0

    try:
        # 格式通常是 "COMMAND N"，如 "UPDATE 1", "DELETE 5"
        parts = result.split()
        if len(parts) >= 2:
            return int(parts[-1])
        return 0
    except (ValueError, IndexError):
        return 0


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全转换为整数

    Args:
        value: 待转换的值
        default: 转换失败时的默认值

    Returns:
        整数值
    """
    if value is None:
        return default

    try:
        return int(value)
    except (ValueError, TypeError):
        return default
