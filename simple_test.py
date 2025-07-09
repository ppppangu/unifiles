#!/usr/bin/env python3
"""
简单的 embedding 测试脚本
"""

import asyncio
import httpx
import yaml

# 读取配置
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

async def test_embedding_service():
    """测试 embedding 服务"""
    print("开始测试 embedding 服务...")
    
    # 获取第一个 embedding 配置
    embedding_config = config["api"]["language_embedding"][0]
    name = embedding_config["name"]
    url = embedding_config["url"]
    key = embedding_config["key"]
    
    print(f"使用配置: name={name}, url={url}")
    
    try:
        # 准备请求头 - 只有当key不为空时才添加Authorization header
        headers = {}
        if key and key.strip():
            headers["Authorization"] = f"Bearer {key}"

        # 配置 HTTP 客户端 - 使用修复后的配置
        timeout = httpx.Timeout(
            connect=30.0,
            read=60.0,
            write=30.0,
            pool=30.0
        )
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=50,
            keepalive_expiry=30.0
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=False,  # 禁用HTTP/2
            verify=False  # 禁用SSL验证
        ) as client:
            response = await client.post(
                url,
                headers=headers,
                json={"model": name, "input": "测试文本"}
            )
            response.raise_for_status()
            result = response.json()

            embedding = result["data"][0]["embedding"]
            print(f"✓ 成功获取 embedding，长度: {len(embedding)}")
            return True
            
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        return False

async def test_concurrent_requests():
    """测试并发请求"""
    print("\n开始测试并发请求...")
    
    embedding_config = config["api"]["language_embedding"][0]
    name = embedding_config["name"]
    url = embedding_config["url"]
    key = embedding_config["key"]
    
    try:
        # 准备请求头 - 只有当key不为空时才添加Authorization header
        headers = {}
        if key and key.strip():
            headers["Authorization"] = f"Bearer {key}"

        # 配置 HTTP 客户端
        timeout = httpx.Timeout(
            connect=30.0,
            read=60.0,
            write=30.0,
            pool=30.0
        )
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=50,
            keepalive_expiry=30.0
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=False,
            verify=False
        ) as client:
            # 创建5个并发请求
            tasks = []
            for i in range(5):
                task = client.post(
                    url,
                    headers=headers,
                    json={"model": name, "input": f"测试文本 {i+1}"}
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            # 检查所有响应
            for i, response in enumerate(responses):
                response.raise_for_status()
                result = response.json()
                embedding = result["data"][0]["embedding"]
                print(f"  请求 {i+1}: 成功，embedding 长度: {len(embedding)}")
            
            print(f"✓ 并发测试成功，处理了 {len(responses)} 个请求")
            return True
            
    except Exception as e:
        print(f"✗ 并发测试失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        return False

async def main():
    print("=" * 50)
    print("Embedding 服务测试")
    print("=" * 50)
    
    # 测试单个请求
    test1 = await test_embedding_service()
    
    # 测试并发请求
    test2 = await test_concurrent_requests()
    
    print("\n" + "=" * 50)
    print("测试结果:")
    print(f"单个请求: {'✓ 成功' if test1 else '✗ 失败'}")
    print(f"并发请求: {'✓ 成功' if test2 else '✗ 失败'}")
    
    if test1 and test2:
        print("\n🎉 所有测试通过！LocalProtocolError 问题已修复。")
    else:
        print("\n❌ 部分测试失败。")

if __name__ == "__main__":
    asyncio.run(main())
