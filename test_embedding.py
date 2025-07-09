#!/usr/bin/env python3
"""
测试 embedding 功能的脚本
用于验证 LocalProtocolError 问题是否已修复
"""

import asyncio
import httpx
from mineru_process import embedding_text
from singleton_embedding import get_latest_embedding_instance
from loguru import logger

async def test_single_embedding():
    """测试单个 embedding 请求"""
    try:
        logger.info("开始测试单个 embedding 请求...")
        
        # 测试文本
        test_text = "这是一个测试文本，用于验证 embedding 功能是否正常工作。"
        
        # 调用 embedding_text 函数
        result = await embedding_text(test_text, 0, "text", "bge-m3")
        
        index, embedding, text, type_str = result
        logger.info(f"Embedding 成功: index={index}, type={type_str}, embedding_length={len(embedding)}")
        logger.info(f"返回文本: {text[:50]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"单个 embedding 测试失败: {str(e)}, 错误类型: {type(e).__name__}")
        return False

async def test_concurrent_embedding():
    """测试并发 embedding 请求"""
    try:
        logger.info("开始测试并发 embedding 请求...")
        
        # 测试文本列表
        test_texts = [
            "第一个测试文本",
            "第二个测试文本", 
            "第三个测试文本",
            "第四个测试文本",
            "第五个测试文本"
        ]
        
        # 创建并发任务
        tasks = []
        for i, text in enumerate(test_texts):
            task = embedding_text(text, i, "text", "bge-m3")
            tasks.append(task)
        
        # 执行并发请求
        results = await asyncio.gather(*tasks)
        
        logger.info(f"并发 embedding 成功: 处理了 {len(results)} 个文本")
        for index, embedding, text, type_str in results:
            logger.info(f"  - index={index}, type={type_str}, embedding_length={len(embedding)}")
        
        return True
        
    except Exception as e:
        logger.error(f"并发 embedding 测试失败: {str(e)}, 错误类型: {type(e).__name__}")
        return False

async def test_direct_http_request():
    """测试直接 HTTP 请求"""
    try:
        logger.info("开始测试直接 HTTP 请求...")
        
        # 获取配置
        name, url, key, alias = get_latest_embedding_instance(alias="bge-m3")
        logger.info(f"使用配置: name={name}, url={url}, alias={alias}")
        
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
            response = await client.post(
                url, 
                headers={"Authorization": f"Bearer {key}"}, 
                json={"model": name, "input": "直接HTTP请求测试文本"}
            )
            response.raise_for_status()
            result = response.json()
            
            embedding = result["data"][0]["embedding"]
            logger.info(f"直接 HTTP 请求成功: embedding_length={len(embedding)}")
            
        return True
        
    except Exception as e:
        logger.error(f"直接 HTTP 请求测试失败: {str(e)}, 错误类型: {type(e).__name__}")
        return False

async def main():
    """主测试函数"""
    logger.info("=" * 50)
    logger.info("开始 Embedding 功能测试")
    logger.info("=" * 50)
    
    # 测试1: 单个请求
    test1_result = await test_single_embedding()
    
    # 测试2: 直接HTTP请求
    test2_result = await test_direct_http_request()
    
    # 测试3: 并发请求
    test3_result = await test_concurrent_embedding()
    
    # 汇总结果
    logger.info("=" * 50)
    logger.info("测试结果汇总:")
    logger.info(f"  单个 embedding 请求: {'✓ 成功' if test1_result else '✗ 失败'}")
    logger.info(f"  直接 HTTP 请求: {'✓ 成功' if test2_result else '✗ 失败'}")
    logger.info(f"  并发 embedding 请求: {'✓ 成功' if test3_result else '✗ 失败'}")
    
    if all([test1_result, test2_result, test3_result]):
        logger.info("🎉 所有测试通过！LocalProtocolError 问题已修复。")
        return True
    else:
        logger.error("❌ 部分测试失败，需要进一步调试。")
        return False

if __name__ == "__main__":
    asyncio.run(main())
