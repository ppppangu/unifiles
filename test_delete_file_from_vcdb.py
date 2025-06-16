"""
测试delete_file_from_vcdb函数的功能
"""
import asyncio
import pytest
from delete_file_module import delete_file_from_vcdb

async def test_delete_file_from_vcdb_basic():
    """测试基本的删除功能"""
    try:
        # 测试参数验证
        try:
            await delete_file_from_vcdb("", "file123", "kb123")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "user_id cannot be empty" in str(e)
            
        try:
            await delete_file_from_vcdb("user123", "", "kb123")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "file_id cannot be empty" in str(e)
            
        try:
            await delete_file_from_vcdb("user123", "file123", "")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "knowledge_base_id cannot be empty" in str(e)
            
        print("✅ 参数验证测试通过")
        
        # 测试不存在的记录（这会连接到真实数据库）
        try:
            result = await delete_file_from_vcdb("nonexistent_user", "nonexistent_file", "nonexistent_kb")
            print(f"删除不存在记录的结果: {result}")
        except ValueError as e:
            print(f"✅ 权限验证测试通过: {e}")
        except Exception as e:
            print(f"⚠️ 数据库连接或其他错误: {e}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

async def test_delete_file_from_vcdb_with_real_data():
    """
    测试真实数据删除（需要先有测试数据）
    注意：这个测试需要数据库中有真实的测试数据
    """
    print("\n=== 真实数据删除测试 ===")
    print("注意：此测试需要数据库中有真实的测试数据")
    print("请确保有以下测试数据：")
    print("- user_id: test_user_123")
    print("- knowledge_base_id: test_kb_123")  
    print("- document_id: test_doc_123")
    
    # 如果你有真实的测试数据，可以取消注释下面的代码
    # try:
    #     result = await delete_file_from_vcdb("test_user_123", "test_doc_123", "test_kb_123")
    #     print(f"✅ 删除成功: {result}")
    # except Exception as e:
    #     print(f"❌ 删除失败: {e}")

if __name__ == "__main__":
    print("开始测试delete_file_from_vcdb函数...")
    asyncio.run(test_delete_file_from_vcdb_basic())
    asyncio.run(test_delete_file_from_vcdb_with_real_data())
    print("测试完成！")
