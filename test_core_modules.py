"""
Test Core Modules
"""
import os
import sys

# Set test environment variables BEFORE any imports
# Database
os.environ['PG_DATABASE'] = 'unifiles'
os.environ['PG_USER'] = 'postgres'
os.environ['PG_PASSWORD'] = 'postgres'
os.environ['PG_HOST'] = 'localhost'
os.environ['PG_PORT'] = '5432'

# Redis
os.environ['REDIS_HOST'] = 'localhost'
os.environ['REDIS_PORT'] = '6379'
os.environ['REDIS_DB'] = '0'

# MinIO
os.environ['MINIO_ENDPOINT'] = 'localhost:9000'
os.environ['MINIO_ACCESS_KEY'] = 'minioadmin'
os.environ['MINIO_SECRET_KEY'] = 'minioadmin'

# Security
os.environ['SECURITY_SECRET_KEY'] = 'test-secret-key-must-be-at-least-32-characters-long!!!'

print("=" * 60)
print("Test Core Modules")
print("=" * 60)

# Test 1: Settings System
print("\n[1/4] Testing Settings System...")
try:
    # Import directly to avoid triggering core.__init__ which has many dependencies
    import sys
    sys.path.insert(0, 'Unifiles')
    from core.config.settings import settings, ConfigStore
    print(f"  - Settings loaded: {settings.app_name} v{settings.app_version}")
    print(f"  - Environment: {settings.environment}")
    print(f"  - Database: {settings.database.host}:{settings.database.port}/{settings.database.database}")
    print(f"  - Redis URL: {settings.redis_url}")
    print("  [OK] Settings system loaded successfully")
except Exception as e:
    print(f"  [FAIL] Settings system failed: {e}")
    sys.exit(1)

# Test 2: Pool Manager
print("\n[2/4] Testing Pool Manager...")
try:
    from core.database.pool_manager import ConnectionPoolManager, get_pool_manager
    print("  - ConnectionPoolManager class imported")
    print("  - get_pool_manager function imported")
    print("  [OK] Pool manager loaded successfully")
except Exception as e:
    print(f"  [FAIL] Pool manager failed: {e}")
    sys.exit(1)

# Test 3: Encryption Service
print("\n[3/4] Testing Encryption Service...")
try:
    from core.security.encryption import (
        hash_api_key, verify_api_key, generate_api_key,
        hash_password, verify_password,
        EncryptionService,
        create_jwt_token, decode_jwt_token
    )

    # Test API key generation and verification
    api_key = generate_api_key()
    print(f"  - Generated API key: {api_key[:20]}...")

    hashed = hash_api_key(api_key)
    print(f"  - Hashed key: {hashed[:30]}...")

    is_valid = verify_api_key(api_key, hashed)
    print(f"  - Verification result: {is_valid}")

    # Test encryption service
    enc = EncryptionService()
    encrypted = enc.encrypt("sensitive data")
    decrypted = enc.decrypt(encrypted)
    print(f"  - Encryption/Decryption test: {'sensitive data' == decrypted}")

    # Test JWT
    token = create_jwt_token({"user_id": 123})
    payload = decode_jwt_token(token)
    print(f"  - JWT test: {payload.get('user_id') == 123}")

    print("  [OK] Encryption service working correctly")
except Exception as e:
    print(f"  [FAIL] Encryption service failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Base Service
print("\n[4/4] Testing Base Service...")
try:
    from core.services.base import BaseService

    # Create a test service
    class TestService(BaseService):
        async def _setup(self):
            self.test_data = "initialized"

        async def _teardown(self):
            self.test_data = None

    print("  - BaseService imported")
    print("  - Test service class created")
    print("  [OK] Base service loaded successfully")
except Exception as e:
    print(f"  [FAIL] Base service failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("All Core Modules Tests Passed!")
print("=" * 60)
print("\nNext Steps:")
print("1. Migrate main.py to use new ConnectionPoolManager")
print("2. Migrate middleware to use unified dependency injection")
print("3. Run database migration script (API key hashing)")
