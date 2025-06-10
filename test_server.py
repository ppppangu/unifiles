#!/usr/bin/env python3
"""
Minimal test server to verify upload functionality
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from minio import Minio
import uuid
import io
import yaml
from pathlib import Path

# Load config
def read_config():
    config_path = Path("config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

config = read_config()
minio_config = config["server_components"]["minio"]

async def health(request: Request):
    return JSONResponse({"status": "ok"})

async def upload_minio(request: Request):
    try:
        print("=== Upload request received ===")
        
        # 解析表单数据
        form = await request.form()
        user_id = form.get("user_id")
        upload_file = form.get("upload_file")

        print(f"User ID: {user_id}")
        print(f"File: {upload_file}")

        # 验证文件
        if not upload_file:
            return JSONResponse(
                {"status": "error", "message": "No file provided"}, 
                status_code=400
            )

        filename = upload_file.filename
        if not filename:
            return JSONResponse(
                {"status": "error", "message": "No filename provided"}, 
                status_code=400
            )

        # 读取文件内容
        file_content = await upload_file.read()
        print(f"File: {filename}, Size: {len(file_content)} bytes")

        # 生成UUID
        file_uuid = str(uuid.uuid4())
        object_path = f"default/{file_uuid}/{filename}"

        print(f"Object path: {object_path}")

        # 创建MinIO客户端
        minio_client = Minio(
            f"{minio_config['host']}:{minio_config['port']}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False
        )

        # 检查桶
        bucket_name = minio_config["bucket_name"]
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            print(f"Created bucket: {bucket_name}")

        # 上传文件
        file_stream = io.BytesIO(file_content)
        minio_client.put_object(
            bucket_name,
            object_path,
            file_stream,
            length=len(file_content),
            content_type=upload_file.content_type or "application/octet-stream"
        )

        print(f"File uploaded successfully!")

        # 生成公网URL
        if minio_config.get("use_public_url", False) and minio_config.get("public_url_prefix"):
            public_url = f"{minio_config['public_url_prefix']}/{bucket_name}/{object_path}"
        else:
            public_url = f"http://{minio_config['host']}:{minio_config['port']}/{bucket_name}/{object_path}"

        print(f"Public URL: {public_url}")

        return JSONResponse({
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "file_id": file_uuid,
                "filename": filename,
                "object_path": object_path,
                "public_url": public_url,
                "file_size": len(file_content)
            }
        })

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"status": "error", "message": f"Upload failed: {str(e)}"}, 
            status_code=500
        )

middleware = [
    Middleware(CORSMiddleware, 
               allow_origins=["*"], 
               allow_credentials=True, 
               allow_methods=["*"], 
               allow_headers=["*"],
               expose_headers=["*"]
               )
]

app = Starlette(
    middleware=middleware,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/upload_minio", upload_minio, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    import uvicorn
    print("Starting test server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
