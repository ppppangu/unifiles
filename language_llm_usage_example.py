#!/usr/bin/env python3
"""
使用示例：如何使用新的 language_llm 类型进行负载均衡
"""

from singleton_embedding import get_latest_embedding_instance

def example_language_llm_usage():
    """演示如何使用 language_llm 类型"""
    
    print("=== Language LLM 使用示例 ===\n")
    
    # 方法1: 通过 instance_type 获取 language_llm 实例
    print("1. 通过 instance_type 获取 language_llm 实例:")
    name, url, key, alias = get_latest_embedding_instance(instance_type="language_llm")
    print(f"   模型名称: {name}")
    print(f"   API URL: {url}")
    print(f"   API Key: {key[:15]}...")
    print(f"   别名: {alias}")
    
    # 方法2: 通过 alias 获取特定的 language_llm 实例
    print("\n2. 通过 alias 获取特定实例:")
    name, url, key, alias = get_latest_embedding_instance(alias="Qwen2.5-7B-Instruct")
    print(f"   模型名称: {name}")
    print(f"   API URL: {url}")
    print(f"   API Key: {key[:15]}...")
    print(f"   别名: {alias}")
    
    # 方法3: 演示在实际应用中的使用
    print("\n3. 实际应用示例 - 调用语言模型:")
    
    def call_language_llm(prompt: str, alias: str = None):
        """调用语言LLM的示例函数"""
        try:
            if alias:
                name, url, key, returned_alias = get_latest_embedding_instance(alias=alias)
            else:
                name, url, key, returned_alias = get_latest_embedding_instance(instance_type="language_llm")
            
            print(f"   使用模型: {name} (别名: {returned_alias})")
            print(f"   API URL: {url}")
            print(f"   提示词: {prompt}")
            
            # 这里可以添加实际的API调用代码
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(url, 
            #         headers={"Authorization": f"Bearer {key}"},
            #         json={
            #             "model": name,
            #             "messages": [{"role": "user", "content": prompt}]
            #         })
            #     return response.json()
            
            print("   [模拟] API调用成功")
            return {"status": "success", "model": name}
            
        except Exception as e:
            print(f"   错误: {e}")
            return {"status": "error", "message": str(e)}
    
    # 使用默认的 language_llm 类型
    result1 = call_language_llm("你好，请介绍一下你自己")
    
    # 使用特定的 alias
    result2 = call_language_llm("请解释什么是人工智能", alias="Qwen2.5-7B-Instruct")
    
    print(f"\n   结果1: {result1}")
    print(f"   结果2: {result2}")

def example_all_types():
    """演示所有支持的类型"""
    
    print("\n=== 所有支持的类型示例 ===\n")
    
    types = ["language_embedding", "multimodal_llm", "language_llm"]
    
    for instance_type in types:
        try:
            name, url, key, alias = get_latest_embedding_instance(instance_type=instance_type)
            print(f"{instance_type}:")
            print(f"   模型: {name}")
            print(f"   别名: {alias}")
            print(f"   URL: {url}")
            print()
        except Exception as e:
            print(f"{instance_type}: 错误 - {e}\n")

def example_load_balancing():
    """演示负载均衡功能"""
    
    print("=== 负载均衡示例 ===\n")
    
    print("连续调用 language_llm 类型 5 次，观察负载均衡:")
    for i in range(5):
        name, url, key, alias = get_latest_embedding_instance(instance_type="language_llm")
        print(f"   第 {i+1} 次调用: {alias}")
    
    print("\n连续调用全局负载均衡 5 次，观察在所有类型间的轮换:")
    for i in range(5):
        name, url, key, alias = get_latest_embedding_instance()
        print(f"   第 {i+1} 次调用: {alias} (类型: 根据配置推断)")

if __name__ == "__main__":
    try:
        example_language_llm_usage()
        example_all_types()
        example_load_balancing()
        
        print("\n" + "="*50)
        print("✅ 所有示例运行完成！")
        print("language_llm 类型已成功集成到负载均衡系统中")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ 运行示例时出错: {e}")
