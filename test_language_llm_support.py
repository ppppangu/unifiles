#!/usr/bin/env python3
"""
测试 singleton_embedding.py 对 language_llm 类型的支持
"""

import asyncio
from singleton_embedding import get_latest_embedding_instance

def test_language_llm_type_support():
    """测试 language_llm 类型的负载均衡功能"""
    print("=== 测试 language_llm 类型支持 ===")
    
    try:
        # 测试通过 instance_type 获取 language_llm 实例
        name, url, key, alias = get_latest_embedding_instance(instance_type="language_llm")
        print(f"✅ 通过 instance_type='language_llm' 获取成功:")
        print(f"   Name: {name}")
        print(f"   URL: {url}")
        print(f"   Key: {key[:10]}...")  # 只显示前10个字符
        print(f"   Alias: {alias}")
        
        # 验证返回的配置是否符合预期
        expected_name = "Qwen/Qwen2.5-7B-Instruct"
        expected_alias = "Qwen2.5-7B-Instruct"
        
        if name == expected_name and alias == expected_alias:
            print("✅ 返回的配置符合预期")
        else:
            print(f"⚠️ 返回的配置与预期不符:")
            print(f"   期望 name: {expected_name}, 实际: {name}")
            print(f"   期望 alias: {expected_alias}, 实际: {alias}")
            
    except Exception as e:
        print(f"❌ 通过 instance_type='language_llm' 获取失败: {e}")
        return False
    
    try:
        # 测试通过 alias 获取 language_llm 实例
        name, url, key, alias = get_latest_embedding_instance(alias="Qwen2.5-7B-Instruct")
        print(f"\n✅ 通过 alias='Qwen2.5-7B-Instruct' 获取成功:")
        print(f"   Name: {name}")
        print(f"   URL: {url}")
        print(f"   Key: {key[:10]}...")
        print(f"   Alias: {alias}")
        
    except Exception as e:
        print(f"❌ 通过 alias='Qwen2.5-7B-Instruct' 获取失败: {e}")
        return False
    
    return True

def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n=== 测试向后兼容性 ===")
    
    try:
        # 测试原有的 language_embedding 类型仍然工作
        name, url, key, alias = get_latest_embedding_instance(instance_type="language_embedding")
        print(f"✅ language_embedding 类型仍然工作:")
        print(f"   Name: {name}")
        print(f"   Alias: {alias}")
        
        # 测试原有的 multimodal_llm 类型仍然工作
        name, url, key, alias = get_latest_embedding_instance(instance_type="multimodal_llm")
        print(f"✅ multimodal_llm 类型仍然工作:")
        print(f"   Name: {name}")
        print(f"   Alias: {alias}")
        
        # 测试全局负载均衡仍然工作
        name, url, key, alias = get_latest_embedding_instance()
        print(f"✅ 全局负载均衡仍然工作:")
        print(f"   Name: {name}")
        print(f"   Alias: {alias}")
        
    except Exception as e:
        print(f"❌ 向后兼容性测试失败: {e}")
        return False
    
    return True

def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    # 测试不支持的类型
    try:
        get_latest_embedding_instance(instance_type="unsupported_type")
        print("❌ 应该抛出错误但没有抛出")
        return False
    except ValueError as e:
        print(f"✅ 不支持的类型正确抛出错误: {e}")
    
    # 测试不存在的 alias
    try:
        get_latest_embedding_instance(alias="non_existent_alias")
        print("❌ 应该抛出错误但没有抛出")
        return False
    except ValueError as e:
        print(f"✅ 不存在的 alias 正确抛出错误: {e}")
    
    # 测试互斥参数
    try:
        get_latest_embedding_instance(alias="test", instance_type="language_llm")
        print("❌ 应该抛出错误但没有抛出")
        return False
    except ValueError as e:
        print(f"✅ 互斥参数正确抛出错误: {e}")
    
    return True

def test_load_balancing():
    """测试负载均衡功能"""
    print("\n=== 测试负载均衡功能 ===")
    
    try:
        # 连续调用多次，验证负载均衡是否工作
        print("连续调用 language_llm 类型 3 次:")
        for i in range(3):
            name, url, key, alias = get_latest_embedding_instance(instance_type="language_llm")
            print(f"  第 {i+1} 次: {alias}")
        
        print("\n连续调用全局负载均衡 5 次:")
        for i in range(5):
            name, url, key, alias = get_latest_embedding_instance()
            print(f"  第 {i+1} 次: {alias}")
        
        print("✅ 负载均衡功能正常")
        return True
        
    except Exception as e:
        print(f"❌ 负载均衡测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试 singleton_embedding.py 的 language_llm 支持...")
    
    all_tests_passed = True
    
    # 运行所有测试
    tests = [
        test_language_llm_type_support,
        test_backward_compatibility,
        test_error_handling,
        test_load_balancing
    ]
    
    for test_func in tests:
        try:
            result = test_func()
            if not result:
                all_tests_passed = False
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 出现异常: {e}")
            all_tests_passed = False
    
    print(f"\n{'='*50}")
    if all_tests_passed:
        print("🎉 所有测试通过！language_llm 支持已成功添加")
    else:
        print("❌ 部分测试失败，请检查实现")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
