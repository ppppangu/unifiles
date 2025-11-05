"""
用户系统相关类型

包含用户模型、访问密钥等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class UserModel:
    """用户模型"""

    id: str
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    user_status: str = "active"
    user_role: str = "user"
    knowledge_ids: List[str] = field(default_factory=list)
    user_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    def __post_init__(self):
        pass


@dataclass
class AccessKeyModel:
    """访问密钥模型"""

    id: str
    user_id: str
    access_key: str
    name: str
    scopes: List[str] = field(default_factory=lambda: ["read", "write"])
    is_active: bool = True
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    def __post_init__(self):
        pass
