#!/usr/bin/env python3
"""
测试Unifile客户端基础功能
验证客户端代码的正确性，不依赖真实的服务器连接
"""

import sys
from pathlib import Path

# 添加项目根路径
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from unifiles.client import (
        ContentType,
        Document,
        DocumentStatus,
        KnowledgeBase,
        Unifile,
        UnifilesError,
    )

    print("✅ 客户端导入成功")
except ImportError as e:
    print(f"❌ 客户端导入失败: {e}")
    sys.exit(1)


def test_client_initialization():
    """测试客户端初始化"""
    print("\n=== 测试客户端初始化 ===")

    try:
        client = Unifile(api_key="test_key", base_url="http://localhost:8087")
        print("✅ 客户端初始化成功")
        print(f"   API Key: {client.api_key}")
        print(f"   Base URL: {client.base_url}")
        return client
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        return None


def test_document_creation():
    """测试文档对象创建"""
    print("\n=== 测试文档对象创建 ===")

    client = Unifile(api_key="test", base_url="http://test")

    try:
        # 测试文档对象创建
        doc = Document(client, "test_file_123")
        print("✅ 文档对象创建成功")
        print(f"   文档ID: {doc.file_id}")
        print(f"   状态: {doc.status}")

        # 测试内容获取（模拟数据）
        content = doc.get_content()
        print("✅ 文档内容获取成功")
        print(f"   提取ID: {content.get('extraction_id')}")

        # 测试按类型获取内容
        text_content = doc.get_content(ContentType.TEXT)
        image_content = doc.get_content(ContentType.IMAGE)
        print("✅ 分类内容获取成功")
        print(f"   文字类内容类型: {text_content.get('type')}")
        print(f"   图片类内容类型: {image_content.get('type')}")

        return doc
    except Exception as e:
        print(f"❌ 文档对象测试失败: {e}")
        return None


def test_knowledge_base_creation():
    """测试知识库对象创建"""
    print("\n=== 测试知识库对象创建 ===")

    client = Unifile(api_key="test", base_url="http://test")

    try:
        # 测试知识库对象创建
        kb = KnowledgeBase(client, "test_kb_123")
        print("✅ 知识库对象创建成功")
        print(f"   知识库ID: {kb.kb_id}")

        # 测试知识库属性
        print(f"   名称: {kb.name}")
        print(f"   文档数量: {kb.document_count}")

        return kb
    except Exception as e:
        print(f"❌ 知识库对象测试失败: {e}")
        return None


def test_enum_types():
    """测试枚举类型"""
    print("\n=== 测试枚举类型 ===")

    try:
        # 测试文档状态枚举
        statuses = [
            DocumentStatus.UPLOADED,
            DocumentStatus.EXTRACTING,
            DocumentStatus.EXTRACTED,
            DocumentStatus.INDEXING,
            DocumentStatus.INDEXED,
            DocumentStatus.FAILED,
        ]
        print("✅ 文档状态枚举:")
        for status in statuses:
            print(f"   - {status.value}")

        # 测试内容类型枚举
        content_types = [ContentType.TEXT, ContentType.IMAGE]
        print("✅ 内容类型枚举:")
        for content_type in content_types:
            print(f"   - {content_type.value}")

        return True
    except Exception as e:
        print(f"❌ 枚举类型测试失败: {e}")
        return False


def test_api_methods():
    """测试API方法结构"""
    print("\n=== 测试API方法结构 ===")

    client = Unifile(api_key="test", base_url="http://test")

    try:
        # 检查客户端方法是否存在
        methods = [
            "upload_file",
            "get_document",
            "list_files",
            "delete_file",
            "create_knowledge_base",
            "get_knowledge_base",
            "list_knowledge_bases",
            "delete_knowledge_base",
            "quick_process",
        ]

        missing_methods = []
        for method in methods:
            if not hasattr(client, method):
                missing_methods.append(method)
            else:
                print(f"   ✅ {method}")

        if missing_methods:
            print(f"❌ 缺失方法: {missing_methods}")
            return False

        print("✅ 所有API方法都存在")
        return True
    except Exception as e:
        print(f"❌ API方法测试失败: {e}")
        return False


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")

    try:
        # 测试UnifilesError异常
        try:
            raise UnifilesError("测试错误")
        except UnifilesError as e:
            print(f"✅ UnifilesError异常处理正常: {e}")

        return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("🚀 开始Unifile客户端基础功能测试\n")

    test_results = []

    # 运行各项测试
    test_results.append(("客户端初始化", test_client_initialization() is not None))
    test_results.append(("文档对象创建", test_document_creation() is not None))
    test_results.append(("知识库对象创建", test_knowledge_base_creation() is not None))
    test_results.append(("枚举类型", test_enum_types()))
    test_results.append(("API方法结构", test_api_methods()))
    test_results.append(("错误处理", test_error_handling()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")

    passed = 0
    failed = 0

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 个测试通过, {failed} 个测试失败")

    if failed == 0:
        print("🎉 所有测试通过！客户端基础功能正常")
        return True
    print("⚠️ 部分测试失败，需要修复")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
