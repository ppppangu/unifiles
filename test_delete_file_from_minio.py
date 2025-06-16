"""
测试delete_file_from_minio函数的功能
"""
import asyncio
import pytest
from delete_file_module import delete_file_from_minio

async def test_delete_file_from_minio_basic():
    """测试基本的删除功能"""
    try:
        # 测试参数验证
        try:
            await delete_file_from_minio("", "file123", "kb123")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "user_id cannot be empty" in str(e)
            
        try:
            await delete_file_from_minio("user123", "", "kb123")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "file_id cannot be empty" in str(e)
            
        try:
            await delete_file_from_minio("user123", "file123", "")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "knowledge_base_id cannot be empty" in str(e)
            
        print("✅ 参数验证测试通过")
        
        # 测试不存在的文件（这会连接到真实MinIO）
        try:
            result = await delete_file_from_minio("nonexistent_user", "nonexistent_file", "nonexistent_kb")
            print(f"删除不存在文件的结果: {result}")
            if not result:
                print("✅ 正确处理了不存在的文件")
            else:
                print("⚠️ 意外删除了文件")
        except Exception as e:
            print(f"⚠️ MinIO连接或其他错误: {e}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

async def test_delete_file_from_minio_paths():
    """
    测试不同路径的文件删除
    """
    print("\n=== MinIO路径测试 ===")
    print("测试文件路径结构：")
    print("1. 主要路径：{user_id}/knowledgebase/{knowledge_base_id}/{file_id}/")
    print("2. 默认路径：{user_id}/default_file_space/{file_id}/")
    
    test_cases = [
        {
            "user_id": "test_user_123",
            "file_id": "test_file_456", 
            "knowledge_base_id": "test_kb_789",
            "description": "测试主要路径"
        },
        {
            "user_id": "test_user_123",
            "file_id": "test_file_default_456",
            "knowledge_base_id": "test_kb_789", 
            "description": "测试默认路径回退"
        }
    ]
    
    for case in test_cases:
        print(f"\n--- {case['description']} ---")
        print(f"用户ID: {case['user_id']}")
        print(f"文件ID: {case['file_id']}")
        print(f"知识库ID: {case['knowledge_base_id']}")
        
        try:
            result = await delete_file_from_minio(
                case['user_id'], 
                case['file_id'], 
                case['knowledge_base_id']
            )
            print(f"删除结果: {result}")
        except Exception as e:
            print(f"删除失败: {e}")

async def test_minio_connection():
    """测试MinIO连接"""
    print("\n=== MinIO连接测试 ===")
    try:
        from delete_file_module import read_config
        from minio import Minio
        
        config = read_config()
        minio_config = config["server_components"]["minio"]
        
        print(f"MinIO配置:")
        print(f"  Host: {minio_config['host']}:{minio_config['port']}")
        print(f"  Bucket: {minio_config['bucket_name']}")
        print(f"  Access Key: {minio_config['access_key'][:8]}...")
        
        # 创建MinIO客户端
        minio_client = Minio(
            f"{minio_config['host']}:{minio_config['port']}",
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False
        )
        
        # 测试连接
        bucket_name = minio_config["bucket_name"]
        if minio_client.bucket_exists(bucket_name):
            print(f"✅ 成功连接到MinIO，桶 '{bucket_name}' 存在")
            
            # 列出一些对象作为测试
            objects = list(minio_client.list_objects(bucket_name, recursive=False, max_keys=5))
            print(f"桶中前5个对象: {[obj.object_name for obj in objects]}")
            
        else:
            print(f"⚠️ 桶 '{bucket_name}' 不存在")
            
    except Exception as e:
        print(f"❌ MinIO连接测试失败: {e}")

if __name__ == "__main__":
    print("开始测试delete_file_from_minio函数...")
    asyncio.run(test_delete_file_from_minio_basic())
    asyncio.run(test_delete_file_from_minio_paths())
    asyncio.run(test_minio_connection())
    print("测试完成！")
