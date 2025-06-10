#!/usr/bin/env python3
"""
Debug test to isolate the issue
"""

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

try:
    print("Testing basic imports...")
    
    import yaml
    print("✅ yaml imported")
    
    from pathlib import Path
    print("✅ pathlib imported")
    
    import uuid
    print("✅ uuid imported")
    
    import io
    print("✅ io imported")
    
    from minio import Minio
    print("✅ minio imported")
    
    from starlette.applications import Starlette
    print("✅ starlette imported")
    
    print("Testing config loading...")
    config_path = Path("config.yaml")
    if config_path.exists():
        print(f"✅ Config file exists: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("✅ Config loaded")
        
        minio_config = config["server_components"]["minio"]
        print(f"✅ MinIO config: {minio_config['host']}:{minio_config['port']}")
    else:
        print("❌ Config file not found")
    
    print("Testing MinIO connection...")
    minio_client = Minio(
        f"{minio_config['host']}:{minio_config['port']}",
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False
    )
    
    # Test bucket existence
    bucket_name = minio_config["bucket_name"]
    exists = minio_client.bucket_exists(bucket_name)
    print(f"✅ Bucket '{bucket_name}' exists: {exists}")
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("Debug test completed.")
