#!/usr/bin/env python3
"""
Simple test without loguru
"""

print("Starting simple test...")

try:
    import yaml
    from pathlib import Path
    print("✅ Basic imports successful")
    
    # Test config loading
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("✅ Config loaded successfully")
        print(f"MinIO config: {config.get('server_components', {}).get('minio', {})}")
    else:
        print("❌ Config file not found")
        
    # Test MinIO import
    from minio import Minio
    print("✅ MinIO imported successfully")
    
    # Test Starlette import
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    print("✅ Starlette imported successfully")
    
    print("✅ All basic tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("Test completed.")
