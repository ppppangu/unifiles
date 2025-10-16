"""
V1 API 中间件模块
包含各种中间件的实现
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import Request, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

# 导入数据库配置
from unifiles.core.config.env_config import read_pg_config

# 导入格式验证器
from unifiles.core.pipelines.format_validator import FileFormatValidator


class ClientIPMiddleware:
    """客户端IP获取中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            # 获取客户端真实IP地址
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = request.client.host if request.client else "unknown"

            # 将IP地址存储到request.state中
            request.state.client_ip = client_ip

        await self.app(scope, receive, send)


class FileValidationMiddleware:
    """文件检测中间件 - 检测文件格式、大小等"""

    def __init__(self, app, config: Optional[Dict[str, Any]] = None):
        self.app = app
        self.validator = FileFormatValidator(config)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)

            # 只对文件上传相关的路径进行检测
            if self._should_validate_file(request):
                # 获取请求体以检查文件
                try:
                    form = await request.form()
                    files_to_validate = []

                    # 收集所有上传的文件
                    for value in form.values():
                        if isinstance(value, UploadFile):
                            files_to_validate.append(value)

                    # 验证所有文件
                    validation_result = await self._validate_files(files_to_validate)
                    if not validation_result["valid"]:
                        # 返回验证失败响应
                        response = JSONResponse(
                            status_code=400,
                            content={
                                "error": "File validation failed",
                                "message": validation_result["message"],
                                "details": validation_result["details"],
                            },
                        )
                        await response(scope, receive, send)
                        return

                    # 将验证结果存储到request.state中供后续使用
                    request.state.file_validation = validation_result

                except Exception as e:
                    # 文件解析失败
                    response = JSONResponse(
                        status_code=400,
                        content={
                            "error": "File parsing failed",
                            "message": f"Unable to parse uploaded files: {e!s}",
                        },
                    )
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)

    def _should_validate_file(self, request: Request) -> bool:
        """判断是否需要进行文件验证"""
        # 写死的路径检测逻辑
        # NOTE: /files 端点使用自己的验证逻辑（FileSecurityValidator），
        # 不在中间件层面验证，以避免消耗request body
        file_upload_paths = [
            "/v1/documents/upload",
            "/v1/documents/process",
            "/v1/files/upload",
            # TODO: 添加更多需要文件验证的路径
            # NOTE: /files 端点已经在service层有验证，不需要中间件验证
        ]

        path = request.url.path
        method = request.method

        # 只对POST/PUT请求的特定路径进行验证
        # /files 端点不在此列表中，因为它有自己的验证逻辑
        return method in ["POST", "PUT"] and any(
            path.startswith(upload_path) for upload_path in file_upload_paths
        )

    async def _validate_files(self, files: List[UploadFile]) -> Dict[str, Any]:
        """验证上传的文件列表"""
        if not files:
            return {
                "valid": False,
                "message": "No files provided",
                "details": {"error_type": "no_files"},
            }

        validation_results = []
        all_valid = True

        for file in files:
            result = await self._validate_single_file(file)
            validation_results.append(
                {
                    "filename": file.filename,
                    "valid": result["valid"],
                    "issues": result.get("issues", []),
                }
            )
            if not result["valid"]:
                all_valid = False

        if all_valid:
            return {
                "valid": True,
                "message": "All files passed validation",
                "details": {"validated_files": validation_results},
            }
        failed_files = [r for r in validation_results if not r["valid"]]
        return {
            "valid": False,
            "message": f"{len(failed_files)} files failed validation",
            "details": {
                "failed_files": failed_files,
                "all_results": validation_results,
            },
        }

    async def _validate_single_file(self, file: UploadFile) -> Dict[str, Any]:
        """验证单个文件"""
        issues = []

        # 1. 文件名检测
        if not file.filename:
            issues.append("Missing filename")
            return {"valid": False, "issues": issues}

        # 2. 使用FileFormatValidator进行文件类型验证
        if not self.validator.validate_file_type(file.filename):
            file_ext = Path(file.filename).suffix.lower()
            issues.append(f"Unsupported file extension: {file_ext}")

        # 3. 文件大小检测和内容验证
        file_size = await self._get_file_size(file)

        # 读取文件内容进行验证
        file_content = await file.read()
        # 重置文件指针
        await file.seek(0)

        # 使用FileFormatValidator进行内容验证
        content_validation = await self.validator.validate_file_content(
            file_content, file.filename
        )

        if not content_validation["is_valid"]:
            issues.extend(content_validation["errors"])

        # TODO: 添加更多检测逻辑占位符
        # 6. 病毒扫描 (占位符)
        # virus_scan = await self._scan_for_virus(file)
        # if not virus_scan['clean']:
        #     issues.append('File failed virus scan')

        # 7. 文件完整性检测 (占位符)
        # integrity_check = await self._check_file_integrity(file)
        # if not integrity_check['valid']:
        #     issues.append('File integrity check failed')

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "file_info": {
                "filename": file.filename,
                "size": file_size,
                "content_type": file.content_type,
                "extension": Path(file.filename).suffix.lower(),
                "category": self.validator.get_file_category(file.filename),
            },
        }

    async def _get_file_size(self, file: UploadFile) -> int:
        """获取文件大小"""
        # 保存当前位置
        current_position = file.file.tell()
        # 移动到文件末尾
        file.file.seek(0, 2)
        size = file.file.tell()
        # 恢复原来的位置
        file.file.seek(current_position)
        return size

    # TODO: 占位符方法，待实现

    async def _scan_for_virus(self, file: UploadFile) -> Dict[str, Any]:
        """病毒扫描 (占位符)"""
        # TODO: 集成病毒扫描引擎
        # 例如：ClamAV 或其他反病毒解决方案
        return {"clean": True}

    async def _check_file_integrity(self, file: UploadFile) -> Dict[str, Any]:
        """文件完整性检查 (占位符)"""
        # TODO: 实现文件完整性检查
        # 例如：校验和验证，文件头部验证等
        return {"valid": True}


class AuthMiddleware:
    """认证中间件 - 处理Bearer Token认证"""

    def __init__(self, app):
        self.app = app
        self.pg_config = read_pg_config()
        self._connection_pool = None

        # 不需要认证的路径
        self.public_paths = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/users/create",
            # 可以添加更多公开路径
        }

        # 不需要认证的路径前缀
        self.public_prefixes = {
            "/static/",
            "/users/",  # 允许用户相关操作不需要认证（用于bootstrap首个access key）
            # 可以添加更多公开路径前缀
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)

            # 检查是否需要认证
            if self._should_authenticate(request):
                # 获取Authorization头部
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": "Authentication required",
                            "message": "Missing or invalid Authorization header. Expected format: 'Bearer <token>'",
                        },
                    )
                    await response(scope, receive, send)
                    return

                # 提取token
                token = auth_header[7:]  # 移除 "Bearer " 前缀

                # 验证token并获取user_id
                user_id = await self._validate_token(token)
                if not user_id:
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": "Invalid token",
                            "message": "The provided token is invalid, expired, or has been revoked",
                        },
                    )
                    await response(scope, receive, send)
                    return

                # 将用户ID存储到request.state中
                request.state.user_id = user_id
                request.state.authenticated = True
            else:
                # 公开路径，设置默认用户
                request.state.user_id = "anonymous"
                request.state.authenticated = False

        await self.app(scope, receive, send)

    def _should_authenticate(self, request: Request) -> bool:
        """判断是否需要认证"""
        path = request.url.path

        # 检查是否为公开路径
        if path in self.public_paths:
            return False

        # 检查是否以公开前缀开始
        return all(not path.startswith(prefix) for prefix in self.public_prefixes)

    async def _init_connection_pool(self):
        """初始化数据库连接池（延迟初始化）"""
        if self._connection_pool is None:
            try:
                self._connection_pool = await asyncpg.create_pool(
                    host=self.pg_config["host"],
                    port=self.pg_config["port"],
                    user=self.pg_config["user"],
                    password=self.pg_config["password"],
                    database=self.pg_config["database"],
                    min_size=5,  # 最小连接数
                    max_size=20,  # 最大连接数
                    command_timeout=10.0,  # 命令超时10秒
                    timeout=30.0,  # 连接超时30秒
                )
                logger.info("Auth middleware connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e!s}")
                raise

    async def _validate_token(self, token: str) -> Optional[str]:
        """验证token并返回用户ID"""
        try:
            # 确保连接池已初始化
            if self._connection_pool is None:
                await self._init_connection_pool()

            # 从连接池获取连接
            async with self._connection_pool.acquire() as conn:
                # 使用简化的验证函数，直接返回user_id
                user_id = await conn.fetchval(
                    "SELECT validate_access_key_simple($1)", token
                )
                return user_id
        except asyncpg.exceptions.PostgresError as e:
            # 数据库相关错误
            logger.error(f"Database error during token validation: {e!s}")
            return None
        except asyncpg.exceptions.TooManyConnectionsError as e:
            # 连接池耗尽
            logger.warning(f"Connection pool exhausted: {e!s}")
            return None
        except Exception as e:
            # 其他错误
            logger.error(f"Token validation error: {e!s}")
            return None

    async def close_connection_pool(self):
        """关闭连接池"""
        if self._connection_pool is not None:
            await self._connection_pool.close()
            self._connection_pool = None
            logger.info("Auth middleware connection pool closed")


# 其他中间件示例：

# class AuthMiddleware:
#     """认证中间件 - 处理Bearer Token"""
#
#     def __init__(self, app):
#         self.app = app
#
#     async def __call__(self, scope, receive, send):
#         if scope["type"] == "http":
#             request = Request(scope, receive)
#             # 获取Authorization头部
#             auth_header = request.headers.get("Authorization")
#             if auth_header and auth_header.startswith("Bearer "):
#                 token = auth_header[7:]  # 移除 "Bearer " 前缀
#                 # TODO: 验证token并获取用户信息
#                 # user_info = await validate_token(token)
#                 # request.state.user_id = user_info.user_id
#                 request.state.token = token
#             else:
#                 request.state.user_id = "default"
#                 request.state.token = None
#
#         await self.app(scope, receive, send)
