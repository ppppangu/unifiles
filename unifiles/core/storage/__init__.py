"""
storage最简实现占位符，不实现任何功能
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional


class FakeBackend:
    """假存储后端，占位符实现"""

    async def upload_file(
        self,
        object_path: str,
        content: bytes,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """假上传，返回假路径"""
        return object_path  # 返回输入路径作为假存储路径

    def get_access_url(
        self,
        object_path: str,
        access_type: str = "presigned",
        expires_in_hours: Optional[int] = None,
    ) -> str:
        """假访问URL"""
        return f"http://placeholder-storage/{object_path}"

    async def delete_file(self, object_path: str) -> bool:
        """假删除"""
        return True  # 假成功

    def get_storage_type(self) -> str:
        """存储类型"""
        return "placeholder"

    def get_metrics(self) -> Dict[str, Any]:
        """假指标"""
        return {"type": "placeholder", "status": "mock"}


class Storage:
    """占位符存储管理器"""

    def __init__(self):
        self._default_backend = FakeBackend()

    async def get_default_backend(self) -> FakeBackend:
        """获取默认后端"""
        return self._default_backend

    async def get_backend(self, config_id: str) -> FakeBackend:
        """获取指定后端，使用默认"""
        return self._default_backend

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {"status": "healthy", "type": "placeholder"}


def get_storage() -> Storage:
    """获取存储实例"""
    return Storage()


async def get_initialized_storage():
    """占位符：仅创建 storage 文件夹，无其他功能"""
    # 计算项目根目录
    root_path = Path(__file__).parent.parent.parent.parent
    storage_path = root_path / "storage"
    storage_path.mkdir(exist_ok=True)
    # 初始化存储实例
    get_storage()
