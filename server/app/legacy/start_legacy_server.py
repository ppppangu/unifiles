#!/usr/bin/env python3
"""
Legacy 版本服务器启动脚本
用于启动迁移后的 legacy 版本文件服务器

启动命令：
uv run python server/app/legacy/start_legacy_server.py

或者直接使用 uvicorn：
uv run uvicorn server.app.legacy.main:app --http httptools --host 0.0.0.0 --port 8087 --log-level debug --access-log
"""

import sys
import os
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    
    # 启动服务器
    uvicorn.run(
        "server.app.legacy.main:app",
        host="0.0.0.0",
        port=8087,
        log_level="debug",
        access_log=True,
        reload=False  # 生产环境建议设为 False
    )