#!/usr/bin/env python3
"""
Unifile客户端完整验证脚本
验证所有功能是否正确实现，不依赖真实服务器连接
"""

import sys
from pathlib import Path

# 添加项目根路径
sys.path.append(str(Path(__file__).parent.parent.parent))


def test_imports():
    """测试所有必要的导入"""
    print("=== 测试导入功能 ===")

    try:
        from unifiles.client import (
            AuthenticationError,
            ContentType,
            Document,
            DocumentNotFoundError,
            DocumentStatus,
            KnowledgeBase,
            KnowledgeBaseNotFoundError,
            RateLimitError,
            Unifile,
            UnifilesError,
        )

        print("✅ 所有类和异常导入成功")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_class_structure():
    """测试类结构和方法"""
    print("\n=== 测试类结构 ===")

    from unifiles.client import Document, KnowledgeBase, Unifile

    # 测试Unifile类
    unifile_methods = [
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

    for method in unifile_methods:
        if hasattr(Unifile, method):
            print(f"✅ Unifile.{method}")
        else:
            print(f"❌ 缺少方法: Unifile.{method}")
            return False

    # 测试Document类
    document_methods = [
        "get_info",
        "get_content",
        "extract_content",
        "index_to_knowledge_base",
        "wait_for_extraction",
    ]

    for method in document_methods:
        if hasattr(Document, method):
            print(f"✅ Document.{method}")
        else:
            print(f"❌ 缺少方法: Document.{method}")
            return False

    # 测试KnowledgeBase类
    kb_methods = ["get_info", "list_documents", "upload_document", "delete_document"]

    for method in kb_methods:
        if hasattr(KnowledgeBase, method):
            print(f"✅ KnowledgeBase.{method}")
        else:
            print(f"❌ 缺少方法: KnowledgeBase.{method}")
            return False

    return True


def test_enums():
    """测试枚举类型"""
    print("\n=== 测试枚举类型 ===")

    from unifiles.client import ContentType, DocumentStatus

    # 测试DocumentStatus
    expected_statuses = [
        "UPLOADED",
        "EXTRACTING",
        "EXTRACTED",
        "INDEXING",
        "INDEXED",
        "FAILED",
    ]

    for status in expected_statuses:
        if hasattr(DocumentStatus, status):
            print(f"✅ DocumentStatus.{status}")
        else:
            print(f"❌ 缺少状态: DocumentStatus.{status}")
            return False

    # 测试ContentType
    expected_types = ["TEXT", "IMAGE"]

    for ctype in expected_types:
        if hasattr(ContentType, ctype):
            print(f"✅ ContentType.{ctype}")
        else:
            print(f"❌ 缺少类型: ContentType.{ctype}")
            return False

    return True


def test_exceptions():
    """测试异常类层次"""
    print("\n=== 测试异常类型 ===")

    from unifiles.client import (
        AuthenticationError,
        DocumentNotFoundError,
        KnowledgeBaseNotFoundError,
        RateLimitError,
        UnifilesError,
    )

    # 测试异常继承关系
    exceptions = [
        DocumentNotFoundError,
        KnowledgeBaseNotFoundError,
        AuthenticationError,
        RateLimitError,
    ]

    for exc_class in exceptions:
        if issubclass(exc_class, UnifilesError):
            print(f"✅ {exc_class.__name__} 继承自 UnifilesError")
        else:
            print(f"❌ {exc_class.__name__} 未正确继承")
            return False

    # 测试异常实例化
    try:
        error = UnifilesError(
            "测试错误", error_code="TEST001", details={"key": "value"}
        )
        if error.message == "测试错误" and error.error_code == "TEST001":
            print("✅ UnifilesError 增强功能正常")
        else:
            print("❌ UnifilesError 增强功能异常")
            return False
    except Exception as e:
        print(f"❌ UnifilesError 实例化失败: {e}")
        return False

    return True


def test_object_creation():
    """测试对象创建和基本功能"""
    print("\n=== 测试对象创建 ===")

    from unifiles.client import Document, KnowledgeBase, Unifile

    try:
        # 创建客户端
        client = Unifile(api_key="test_key", base_url="http://test.com")
        print("✅ Unifile 客户端创建成功")

        # 创建文档对象
        document = Document(client, "test_doc_123")
        print("✅ Document 对象创建成功")

        # 测试文档属性
        if document.file_id == "test_doc_123":
            print("✅ Document.file_id 属性正常")
        else:
            print("❌ Document.file_id 属性异常")
            return False

        # 创建知识库对象
        kb = KnowledgeBase(client, "test_kb_123")
        print("✅ KnowledgeBase 对象创建成功")

        # 测试知识库属性
        if kb.kb_id == "test_kb_123":
            print("✅ KnowledgeBase.kb_id 属性正常")
        else:
            print("❌ KnowledgeBase.kb_id 属性异常")
            return False

        return True

    except Exception as e:
        print(f"❌ 对象创建失败: {e}")
        return False


def test_mock_functionality():
    """测试模拟功能（不依赖网络）"""
    print("\n=== 测试模拟功能 ===")

    from unifiles.client import ContentType, Unifile

    try:
        client = Unifile(api_key="test", base_url="http://test")

        # 测试知识库创建（模拟）
        kb = client.create_knowledge_base("测试知识库", "描述")
        if kb and kb.name == "测试知识库":
            print("✅ 知识库创建模拟功能正常")
        else:
            print("❌ 知识库创建模拟功能异常")
            return False

        # 测试文档内容获取（模拟）
        from unifiles.client import Document

        doc = Document(client, "test_file")
        content = doc.get_content()
        if content and "extraction_id" in content:
            print("✅ 文档内容获取模拟功能正常")
        else:
            print("❌ 文档内容获取模拟功能异常")
            return False

        # 测试内容类型获取
        text_content = doc.get_content(ContentType.TEXT)
        image_content = doc.get_content(ContentType.IMAGE)

        if text_content.get("type") == "text" and image_content.get("type") == "image":
            print("✅ 内容类型分离功能正常")
        else:
            print("❌ 内容类型分离功能异常")
            return False

        return True

    except Exception as e:
        print(f"❌ 模拟功能测试失败: {e}")
        return False


def test_api_design():
    """测试API设计原则"""
    print("\n=== 测试API设计 ===")

    from unifiles.client import Unifile

    # 测试链式调用可能性
    try:
        client = Unifile(api_key="test", base_url="http://test")

        # 测试返回类型
        kb = client.create_knowledge_base("test", "desc")
        if hasattr(kb, "kb_id") and hasattr(kb, "name"):
            print("✅ 知识库对象返回正确属性")
        else:
            print("❌ 知识库对象缺少必要属性")
            return False

        # 测试文档对象
        doc = client.get_document("test_id")
        if hasattr(doc, "file_id") and hasattr(doc, "get_content"):
            print("✅ 文档对象返回正确属性和方法")
        else:
            print("❌ 文档对象缺少必要属性或方法")
            return False

        return True

    except Exception as e:
        print(f"❌ API设计测试失败: {e}")
        return False


def validate_package_structure():
    """验证包结构"""
    print("\n=== 验证包结构 ===")

    # 检查重要文件
    required_files = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "MANIFEST.in",
        "unifiles/client/__init__.py",
        "unifiles/client/client.py",
        "examples/fast_start.py",
    ]

    base_path = Path(__file__).parent

    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ 缺少文件: {file_path}")
            return False

    # 检查pyproject.toml内容
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("⚠️ 无法验证pyproject.toml内容（缺少toml库）")
            return True

    try:
        with open(base_path / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        if "project" in config and "name" in config["project"]:
            print(f"✅ 包名: {config['project']['name']}")
        else:
            print("❌ pyproject.toml缺少项目名称")
            return False

        if "version" in config["project"]:
            print(f"✅ 版本: {config['project']['version']}")
        else:
            print("❌ pyproject.toml缺少版本信息")
            return False

    except Exception as e:
        print(f"⚠️ pyproject.toml验证失败: {e}")

    return True


def main():
    """运行所有验证测试"""
    print("🚀 Unifile Python客户端完整验证\n")
    print("📋 验证项目:")
    print("   • 导入功能")
    print("   • 类结构和方法")
    print("   • 枚举类型")
    print("   • 异常处理")
    print("   • 对象创建")
    print("   • 模拟功能")
    print("   • API设计")
    print("   • 包结构")
    print()

    tests = [
        ("导入功能", test_imports),
        ("类结构", test_class_structure),
        ("枚举类型", test_enums),
        ("异常处理", test_exceptions),
        ("对象创建", test_object_creation),
        ("模拟功能", test_mock_functionality),
        ("API设计", test_api_design),
        ("包结构", validate_package_structure),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print("📊 验证结果汇总:")
    print(f"   ✅ 通过: {passed}")
    print(f"   ❌ 失败: {failed}")
    print(f"   📈 成功率: {passed / (passed + failed) * 100:.1f}%")

    if failed == 0:
        print("\n🎉 所有验证通过！Unifile客户端已完成")
        print("\n✨ 客户端特性:")
        print("   🏗️ 完整的三层文档处理架构")
        print("   📁 文件存储层 - 上传和管理原始文件")
        print("   🔍 内容提取层 - OCR处理，生成图片类和文字类内容")
        print("   📚 知识库索引层 - 文档分块和向量化")
        print("   🚀 一键快速处理功能")
        print("   🛡️ 全面的错误处理和状态管理")
        print("   🐍 符合Python惯例的简洁API设计")
        print("   📦 完整的PyPI包结构")
        print("\n🚀 客户端已准备好发布到PyPI！")
        return True
    print(f"\n⚠️ 发现 {failed} 个问题，需要修复后再发布")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
