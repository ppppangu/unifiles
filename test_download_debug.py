#!/usr/bin/env python3
"""
测试文件下载功能的调试脚本
用于诊断下载问题的根本原因
"""

import asyncio
import httpx
import tempfile
import os
from pathlib import Path
from loguru import logger
from datetime import datetime

# 配置日志
log_path = Path(__file__).parent / "logs"
log_path.mkdir(exist_ok=True)
logger.add(log_path / f"download_debug_{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")

async def test_basic_connectivity(url: str):
    """测试基本网络连接"""
    logger.info(f"=== 测试基本连接性: {url} ===")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            logger.info(f"✓ 基本连接成功: {response.status_code}")
            logger.info(f"响应头: {dict(response.headers)}")
            return True
    except Exception as e:
        logger.error(f"✗ 基本连接失败: {str(e)}")
        return False

async def test_head_request(url: str):
    """测试HEAD请求"""
    logger.info(f"=== 测试HEAD请求: {url} ===")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.head(url)
            logger.info(f"✓ HEAD请求成功: {response.status_code}")
            logger.info(f"Content-Length: {response.headers.get('content-length', 'unknown')}")
            logger.info(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            return True
    except Exception as e:
        logger.error(f"✗ HEAD请求失败: {str(e)}")
        return False

async def test_download_with_different_configs(url: str):
    """使用不同配置测试下载"""
    logger.info(f"=== 测试不同HTTP客户端配置: {url} ===")
    
    configs = [
        {
            "name": "默认配置",
            "config": {}
        },
        {
            "name": "禁用SSL验证",
            "config": {"verify": False}
        },
        {
            "name": "增加超时时间",
            "config": {"timeout": 120.0}
        },
        {
            "name": "添加User-Agent",
            "config": {
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            }
        },
        {
            "name": "完整配置",
            "config": {
                "timeout": httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0),
                "verify": False,
                "follow_redirects": True,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "*/*"
                }
            }
        }
    ]
    
    for config_info in configs:
        logger.info(f"--- 测试配置: {config_info['name']} ---")
        try:
            async with httpx.AsyncClient(**config_info['config']) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                logger.info(f"✓ {config_info['name']} 成功: {response.status_code}")
                logger.info(f"内容大小: {len(response.content)} 字节")
                
                # 如果成功，保存一个小的测试文件
                if len(response.content) > 0:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.test') as tmp_file:
                        tmp_file.write(response.content[:1024])  # 只保存前1KB用于测试
                        logger.info(f"测试文件保存到: {tmp_file.name}")
                        os.unlink(tmp_file.name)  # 立即删除
                
                return True
                
        except Exception as e:
            logger.error(f"✗ {config_info['name']} 失败: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
    
    return False

async def test_step_by_step_download(url: str):
    """分步骤测试下载过程"""
    logger.info(f"=== 分步骤测试下载: {url} ===")
    
    try:
        # 步骤1: 创建客户端
        logger.info("步骤1: 创建HTTP客户端")
        timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*'
        }
        
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
            verify=False
        ) as client:
            logger.info("✓ HTTP客户端创建成功")
            
            # 步骤2: 发送请求
            logger.info("步骤2: 发送GET请求")
            response = await client.get(url)
            logger.info(f"✓ 请求发送成功，状态码: {response.status_code}")
            
            # 步骤3: 检查状态
            logger.info("步骤3: 检查响应状态")
            response.raise_for_status()
            logger.info("✓ 响应状态正常")
            
            # 步骤4: 检查内容
            logger.info("步骤4: 检查响应内容")
            content_length = len(response.content)
            logger.info(f"✓ 内容长度: {content_length} 字节")
            
            if content_length == 0:
                logger.error("✗ 响应内容为空")
                return False
            
            # 步骤5: 保存文件
            logger.info("步骤5: 保存到临时文件")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(response.content)
                temp_path = tmp_file.name
            
            # 步骤6: 验证文件
            logger.info("步骤6: 验证保存的文件")
            if os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                logger.info(f"✓ 文件保存成功，大小: {file_size} 字节")
                os.unlink(temp_path)  # 清理
                return True
            else:
                logger.error("✗ 文件保存失败")
                return False
                
    except Exception as e:
        logger.error(f"✗ 分步骤测试失败: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"完整错误信息:\n{traceback.format_exc()}")
        return False

async def main():
    """主测试函数"""
    # 测试URL - 可以替换为实际的问题URL
    test_urls = [
        "https://httpbin.org/get",  # 简单测试URL
        "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",  # 测试PDF
        # 添加你遇到问题的实际URL
    ]
    
    for url in test_urls:
        logger.info(f"\n{'='*60}")
        logger.info(f"开始测试URL: {url}")
        logger.info(f"{'='*60}")
        
        # 运行所有测试
        await test_basic_connectivity(url)
        await test_head_request(url)
        await test_download_with_different_configs(url)
        await test_step_by_step_download(url)
        
        logger.info(f"URL {url} 测试完成\n")

if __name__ == "__main__":
    logger.info("开始下载调试测试")
    asyncio.run(main())
    logger.info("下载调试测试完成")
