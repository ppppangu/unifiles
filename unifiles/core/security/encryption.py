"""
加密服务 - 敏感数据保护

功能：
- API密钥Hash（bcrypt）
- 密码Hash（bcrypt）
- 对称加密（Fernet）
- JWT生成和验证
- 安全随机字符串生成
"""

import secrets
from typing import Optional
from datetime import datetime, timedelta

from loguru import logger

try:
    from passlib.context import CryptContext
except ImportError:
    logger.warning("passlib not installed, password hashing will not be available")
    CryptContext = None

try:
    from cryptography.fernet import Fernet
except ImportError:
    logger.warning("cryptography not installed, encryption will not be available")
    Fernet = None

try:
    import jwt
except ImportError:
    logger.warning("PyJWT not installed, JWT functions will not be available")
    jwt = None

from unifiles.config import settings


# ===== Password/API Key Hashing =====

# 密码哈希上下文（使用bcrypt）
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.security.api_key_hash_rounds
) if CryptContext else None


def hash_api_key(api_key: str) -> str:
    """
    Hash API密钥（用于存储）

    Args:
        api_key: 原始API密钥

    Returns:
        Hash后的密钥（bcrypt格式）

    Note:
        bcrypt has a 72-byte limit, so we truncate if necessary
    """
    if not pwd_context:
        raise RuntimeError("passlib not available")

    # bcrypt限制：最多72字节
    api_key_bytes = api_key.encode('utf-8')[:72]
    return pwd_context.hash(api_key_bytes.decode('utf-8', errors='ignore'))


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    验证API密钥

    Args:
        plain_key: 用户提供的明文密钥
        hashed_key: 数据库中存储的hash值

    Returns:
        是否匹配

    Note:
        bcrypt has a 72-byte limit, so we truncate if necessary
    """
    if not pwd_context:
        raise RuntimeError("passlib not available")

    try:
        # bcrypt限制：最多72字节（与hash_api_key保持一致）
        plain_key_bytes = plain_key.encode('utf-8')[:72]
        return pwd_context.verify(plain_key_bytes.decode('utf-8', errors='ignore'), hashed_key)
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
        return False


def hash_password(password: str) -> str:
    """Hash用户密码"""
    if not pwd_context:
        raise RuntimeError("passlib not available")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证用户密码"""
    if not pwd_context:
        raise RuntimeError("passlib not available")

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# ===== 对称加密 (Fernet) =====

class EncryptionService:
    """
    对称加密服务（用于加密敏感配置、文件等）

    使用 Fernet（基于AES-128-CBC）
    """

    def __init__(self, key: Optional[bytes] = None):
        """
        初始化加密服务

        Args:
            key: 32字节的密钥（如果为None，使用settings中的secret_key）
        """
        if not Fernet:
            raise RuntimeError("cryptography package not available")

        if key is None:
            # 从settings获取密钥并转换为Fernet格式
            import base64
            key = base64.urlsafe_b64encode(settings.security.secret_key.encode()[:32].ljust(32, b'0'))

        self.cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """
        加密字符串

        Args:
            data: 明文字符串

        Returns:
            Base64编码的加密数据
        """
        encrypted_bytes = self.cipher.encrypt(data.encode())
        return encrypted_bytes.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        解密字符串

        Args:
            encrypted_data: 加密后的Base64字符串

        Returns:
            解密的明文字符串
        """
        decrypted_bytes = self.cipher.decrypt(encrypted_data.encode())
        return decrypted_bytes.decode()


# ===== JWT Token =====

def create_jwt_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    创建JWT Token

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量（默认24小时）
        secret_key: 密钥（默认使用settings中的secret_key）

    Returns:
        JWT字符串
    """
    if not jwt:
        raise RuntimeError("PyJWT not available")

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.security.jwt_expiration_hours)

    to_encode.update({"exp": expire})

    secret = secret_key or settings.security.secret_key

    encoded_jwt = jwt.encode(
        to_encode,
        secret,
        algorithm=settings.security.jwt_algorithm
    )

    return encoded_jwt


def decode_jwt_token(
    token: str,
    secret_key: Optional[str] = None
) -> Optional[dict]:
    """
    解码并验证JWT Token

    Args:
        token: JWT字符串
        secret_key: 密钥（默认使用settings中的secret_key）

    Returns:
        解码后的数据，如果验证失败返回None
    """
    if not jwt:
        raise RuntimeError("PyJWT not available")

    try:
        secret = secret_key or settings.security.secret_key

        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.security.jwt_algorithm]
        )

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None


# ===== API密钥生成 =====

def generate_api_key(prefix: str = "sk_live") -> str:
    """
    生成安全的API密钥

    格式: {prefix}_{随机字符串}

    Args:
        prefix: 密钥前缀（默认sk_live）

    Returns:
        生成的API密钥

    Note:
        Reduced to 24 bytes to stay within bcrypt's 72-byte limit
    """
    # 使用24字节以确保整个密钥（包括前缀）不超过72字节
    random_part = secrets.token_urlsafe(24)
    return f"{prefix}_{random_part}"


def generate_secure_token(length: int = 32) -> str:
    """
    生成安全的随机token

    Args:
        length: token长度（字节数）

    Returns:
        URL安全的随机字符串
    """
    return secrets.token_urlsafe(length)


# ===== 全局实例 =====

# 默认加密服务实例
encryption_service = EncryptionService() if Fernet else None
