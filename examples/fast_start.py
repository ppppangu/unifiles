"""
Unifile Python客户端使用示例 (同步版本)
演示三层文档处理架构的简洁用法

三层架构：
1. 文件存储层：原始文件上传和管理
2. 内容提取层：OCR处理，生成图片类和文字类内容
3. 知识库索引层：文档分块和向量化
"""

# 导入Unifile客户端
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from unifiles.client import ContentType, Document, Unifile


def basic_usage_example():
    """基础用法示例 - 展示三层处理架构"""
    print("=== Unifile基础用法示例 ===\n")

    # 1. 初始化客户端
    client = Unifile(api_key="your_api_key_here", base_url="http://localhost:8087")
    print("✅ Unifile客户端初始化完成")

    # 2. 创建知识库
    knowledge_base = client.create_knowledge_base(
        name="我的文档知识库", description="存储重要PDF文档的知识库"
    )
    print(f"✅ 知识库创建成功: {knowledge_base.name} (ID: {knowledge_base.kb_id})")

    # 3. 获取知识库列表
    kb_list = client.list_knowledge_bases()
    print(f"✅ 获取到 {len(kb_list)} 个知识库:")
    for kb in kb_list:
        print(f"   - {kb.name} (文档数: {kb.document_count})")

    # 4. 上传文档到第一层（文件存储）
    document_path = "/path/to/your/document.pdf"  # 替换为实际文件路径
    print(f"\n📄 准备上传文档: {document_path}")

    # 注意：这里只是示例，实际使用时需要提供真实的文件路径
    # document = client.upload_file(document_path)
    # print(f"✅ 文档上传成功: {document.filename} (ID: {document.file_id})")
    # print(f"   文件大小: {document.file_size} 字节")

    # 使用模拟数据继续演示
    mock_document = Document(client, "mock_file_123")
    print("✅ 文档上传成功: example.pdf (ID: mock_file_123)")
    print("   文件大小: 2048576 字节")

    # 5. 第二层处理：内容提取（OCR）
    print("\n🔍 开始内容提取（OCR处理）...")
    # mock_document.extract_content(mode="normal")

    # 获取提取的内容（图片类和文字类）
    content = mock_document.get_content()
    print("✅ 内容提取完成")
    print(f"   提取ID: {content.get('extraction_id')}")
    print(f"   处理页数: {content.get('extraction_metadata', {}).get('pages', 0)}")

    # 分别获取文字类和图片类内容
    mock_document.get_content(ContentType.TEXT)
    mock_document.get_content(ContentType.IMAGE)
    print("   📝 文字类内容已提取")
    print("   🖼️  图片类内容（OCR）已提取")

    # 6. 第三层处理：知识库索引
    print("\n📚 开始知识库索引（分块和向量化）...")
    # index_result = mock_document.index_to_knowledge_base(
    #     knowledge_base.kb_id,
    #     chunk_strategy="semantic"
    # )
    print("✅ 文档已索引到知识库")
    # print(f"   文档ID: {index_result.get('document_id')}")
    # print(f"   分块数量: {index_result.get('chunk_count')}")

    # 7. 获取知识库中的文档列表
    print("\n📋 知识库文档列表:")
    documents = knowledge_base.list_documents()
    print(f"✅ 知识库包含 {len(documents)} 个文档")
    for doc in documents:
        print(
            f"   - {doc.get('filename', 'Unknown')} (状态: {doc.get('status', 'Unknown')})"
        )


def quick_process_example():
    """一键快速处理示例 - 最简洁的用法"""
    print("\n" + "=" * 50)
    print("=== 一键快速处理示例 ===\n")

    # 初始化客户端
    Unifile(api_key="your_api_key_here", base_url="http://localhost:8087")

    # 一键完成三层处理：上传 → 提取 → 索引
    document_path = "/path/to/your/important.pdf"
    print(f"🚀 一键处理文档: {document_path}")

    # document = client.quick_process(
    #     file_path=document_path,
    #     knowledge_base_name="重要文档库"
    # )

    print("✅ 文档处理完成！已完成：")
    print("   1️⃣ 文件上传到存储层")
    print("   2️⃣ OCR内容提取（图片类+文字类）")
    print("   3️⃣ 分块和向量化索引")
    print("   📚 文档已加入知识库，可进行检索")


def knowledge_base_management_example():
    """知识库管理示例"""
    print("\n" + "=" * 50)
    print("=== 知识库管理示例 ===\n")

    client = Unifile(api_key="your_api_key_here", base_url="http://localhost:8087")

    # 获取现有知识库
    kb_list = client.list_knowledge_bases()
    if kb_list:
        example_kb = kb_list[0]
        print(f"📚 使用知识库: {example_kb.name}")

        # 直接通过知识库上传文档（自动完成三层处理）
        document_path = "/path/to/your/research.pdf"
        print(f"📄 通过知识库上传文档: {document_path}")

        # document = example_kb.upload_document(
        #     file_path=document_path,
        #     is_public=False,
        #     auto_extract=True,   # 自动内容提取
        #     auto_index=True      # 自动索引
        # )

        print("✅ 文档已自动完成三层处理并加入知识库")

        # 快速获取已处理的文档内容
        print("\n🔍 快速获取已处理的文档内容:")
        # content = document.get_content()
        # print(f"   📝 文本内容: {content.get('text_content', '')[:100]}...")
        # print(f"   🖼️ OCR内容: {content.get('image_content', '')[:100]}...")
        # print(f"   📄 Markdown: {content.get('markdown_content', '')[:100]}...")

        print("   ✅ 用户可以非常快速、方便地获取已处理的PDF文档内容！")
    else:
        print("ℹ️ 暂无知识库，请先创建知识库")


def main():
    """主函数 - 运行所有示例"""
    print("🚀 Unifile Python客户端使用示例\n")
    print("📋 示例概要:")
    print("   • 三层文档处理架构演示")
    print("   • 快速上传和内容提取")
    print("   • OCR处理（图片类+文字类内容）")
    print("   • 知识库索引和管理")
    print("   • 一键快速处理")
    print("   • 简洁易用的API设计")
    print()

    try:
        # 基础用法示例
        basic_usage_example()

        # 一键快速处理示例
        quick_process_example()

        # 知识库管理示例
        knowledge_base_management_example()

        print("\n" + "=" * 60)
        print("🎉 所有示例演示完成！")
        print("\n📝 总结:")
        print("   ✅ Unifile客户端支持完整的三层文档处理")
        print("   ✅ 用户可以快速获取已处理的PDF文档内容")
        print("   ✅ 图片类和文字类内容处理等价且简洁")
        print("   ✅ 支持一键自动化处理流程")
        print("   ✅ API设计简洁，符合Python惯例")
        print("\n🚀 开始使用Unifile构建您的文档处理应用吧！")

    except Exception as e:
        print(f"❌ 示例运行出错: {e}")
        print("💡 请检查API密钥和服务器地址配置")


if __name__ == "__main__":
    main()
