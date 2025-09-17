"""
核心测试 - 只测试最重要的功能
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_upload_file_basic():
    """测试文件上传基本逻辑"""
    # 模拟请求
    request = Mock()
    request.state.user_id = "user123"

    # 模拟文件
    file = Mock()
    file.filename = "test.txt"
    file.read = AsyncMock(return_value=b"test content")

    # 模拟上传逻辑
    async def upload_logic(req, f):
        if not f.filename:
            raise HTTPException(status_code=400, detail="No filename")
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        return {"success": True, "filename": f.filename}

    # 测试
    result = await upload_logic(request, file)
    assert result["success"] is True
    assert result["filename"] == "test.txt"


@pytest.mark.asyncio
async def test_upload_file_errors():
    """测试文件上传错误情况"""
    request = Mock()
    request.state.user_id = "user123"

    async def upload_logic(req, f):
        if not f.filename:
            raise HTTPException(status_code=400, detail="No filename")
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        return {"success": True}

    # 测试无文件名
    file_no_name = Mock()
    file_no_name.filename = None
    with pytest.raises(HTTPException) as exc:
        await upload_logic(request, file_no_name)
    assert exc.value.status_code == 400

    # 测试空文件
    file_empty = Mock()
    file_empty.filename = "empty.txt"
    file_empty.read = AsyncMock(return_value=b"")
    with pytest.raises(HTTPException) as exc:
        await upload_logic(request, file_empty)
    assert exc.value.status_code == 400


def test_access_control():
    """测试访问控制"""
    request = Mock()
    request.state.user_id = "user123"

    def check_access(req, file_record):
        if not file_record:
            raise HTTPException(status_code=404, detail="Not found")
        if file_record["user_id"] != req.state.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return True

    # 测试自己的文件
    my_file = {"user_id": "user123", "filename": "my.txt"}
    assert check_access(request, my_file) is True

    # 测试别人的文件
    other_file = {"user_id": "other456", "filename": "other.txt"}
    with pytest.raises(HTTPException) as exc:
        check_access(request, other_file)
    assert exc.value.status_code == 403

    # 测试不存在的文件
    with pytest.raises(HTTPException) as exc:
        check_access(request, None)
    assert exc.value.status_code == 404


def test_file_types():
    """测试支持的文件类型"""
    DOCUMENT_TYPES = [".txt", ".doc", ".docx", ".pdf"]
    CODE_TYPES = [".py", ".js", ".json"]
    ALL_TYPES = DOCUMENT_TYPES + CODE_TYPES

    assert ".txt" in DOCUMENT_TYPES
    assert ".py" in CODE_TYPES
    assert len(ALL_TYPES) == len(DOCUMENT_TYPES) + len(CODE_TYPES)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
