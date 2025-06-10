#!/usr/bin/env python3
"""
Test configuration loading
"""

try:
    print("Testing configuration loading...")
    
    from src.tools import read_config, read_pg_config, read_minio_config, mk_need_path
    print("✅ Tools imported successfully")
    
    config = read_config()
    print("✅ Config loaded successfully")
    print(f"Config keys: {list(config.keys())}")
    
    pg_config = read_pg_config()
    print("✅ PG config loaded successfully")
    print(f"PG host: {pg_config.get('host')}")
    
    minio_config = read_minio_config()
    print("✅ MinIO config loaded successfully")
    print(f"MinIO host: {minio_config.get('host')}")
    print(f"MinIO bucket: {minio_config.get('bucket_name')}")
    
    mk_need_path()
    print("✅ Directories created successfully")
    
    print("✅ All configuration tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
