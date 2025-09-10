#!/usr/bin/env python3
"""
测试v1版本文件上传功能的脚本
"""

import requests
import json
from pathlib import Path
import tempfile


def create_test_file():
    """创建一个测试文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("这是一个测试文件内容\n测试文件上传功能\n")
        return f.name


def test_file_upload():
    """测试文件上传功能"""
    base_url = "http://localhost:8088"
    
    # 创建测试文件
    test_file_path = create_test_file()
    
    try:
        # 测试上传文件
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            data = {'user_id': 'test_user'}
            
            print("正在上传文件...")
            response = requests.post(f"{base_url}/files", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 文件上传成功!")
                print(f"文件ID: {result['file']['file_id']}")
                print(f"文件名: {result['file']['filename']}")
                print(f"公网URL: {result['file']['public_url']}")
                
                # 测试获取文件信息
                file_id = result['file']['file_id']
                print(f"\n正在获取文件信息 {file_id}...")
                info_response = requests.get(f"{base_url}/files/{file_id}")
                
                if info_response.status_code == 200:
                    file_info = info_response.json()
                    print("✅ 获取文件信息成功!")
                    print(f"文件大小: {file_info['file_size']} bytes")
                    print(f"内容类型: {file_info['content_type']}")
                else:
                    print(f"❌ 获取文件信息失败: {info_response.status_code}")
                    print(info_response.text)
                
                # 可选：测试删除文件
                delete_test = input("\n是否测试删除文件? (y/N): ").lower()
                if delete_test == 'y':
                    print(f"正在删除文件 {file_id}...")
                    delete_response = requests.delete(f"{base_url}/files/{file_id}?user_id=test_user")
                    
                    if delete_response.status_code == 200:
                        print("✅ 文件删除成功!")
                    else:
                        print(f"❌ 文件删除失败: {delete_response.status_code}")
                        print(delete_response.text)
                        
            else:
                print(f"❌ 文件上传失败: {response.status_code}")
                print(response.text)
                
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务器正在运行在 http://localhost:8088")
    except Exception as e:
        print(f"❌ 测试过程中出错: {str(e)}")
    finally:
        # 清理测试文件
        Path(test_file_path).unlink()


def test_health_check():
    """测试健康检查"""
    try:
        response = requests.get("http://localhost:8088/health")
        if response.status_code == 200:
            print("✅ 服务器健康检查通过")
            return True
        else:
            print(f"❌ 服务器健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False


def test_supported_file_types():
    """测试支持的文件类型接口"""
    try:
        response = requests.get("http://localhost:8088/files/types")
        if response.status_code == 200:
            result = response.json()
            print("✅ 支持的文件类型:")
            print(f"文档类型: {result['document_types']}")
            print(f"PDF类型: {result['pdf_types']}")
            print(f"代码类型: {result['code_types']}")
            return True
        else:
            print(f"❌ 获取支持文件类型失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 测试支持文件类型时出错: {str(e)}")
        return False


if __name__ == "__main__":
    print("🚀 开始测试文件服务器v1版本功能...\n")
    
    # 测试健康检查
    if not test_health_check():
        exit(1)
        
    print()
    
    # 测试支持的文件类型
    if not test_supported_file_types():
        exit(1)
        
    print()
    
    # 测试文件上传
    test_file_upload()
    
    print("\n🎉 测试完成!")