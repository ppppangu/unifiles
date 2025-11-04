"""
Unifiles Python 客户端 - 快速入门示例

这是一个简单的示例，展示如何使用 Unifiles 客户端：
1. 上传文件
2. 提取内容
3. 创建知识库
4. 索引文档
5. 搜索知识库

使用前请修改下方的 API_KEY 和 FILE_PATH
"""

from pathlib import Path

from unifiles.client import Unifile, UnifilesError

# ============= 配置区域 =============
# 请替换为你的实际 API Key 和文件路径
API_KEY = "[REDACTED]"
BASE_URL = "http://localhost:8088"
FILE_PATH = "./rag.pdf"  # 替换为你要处理的文件路径
KNOWLEDGE_BASE_NAME = "我的第一个知识库"
# ===================================

try:
    print("=" * 60)
    print("Unifiles 客户端演示")
    print("=" * 60)

    # 1. 初始化客户端
    print("\n[1/5] 初始化客户端...")
    client = Unifile(api_key=API_KEY, base_url=BASE_URL)
    print(f"✅ 客户端已连接到: {client.base_url}")

    # 2. 上传文件
    print(f"\n[2/5] 上传文件: {FILE_PATH}")
    doc = client.upload_file(Path(FILE_PATH), is_public=False)
    print("✅ 文件上传成功")
    print(f"   - 文件ID: {doc.file_id}")
    print(f"   - 文件名: {doc.filename}")
    print(f"   - 大小: {doc.file_size} 字节")

    # 3. 提取文件内容（等待完成）
    print("\n[3/5] 提取文件内容（这可能需要一些时间）...")
    result = doc.extract_content(mode="selfhosted", wait=True)
    print("✅ 内容提取完成")

    # 4. 创建知识库并索引文档
    print(f"\n[4/5] 创建知识库: {KNOWLEDGE_BASE_NAME}")
    kb = client.create_knowledge_base(KNOWLEDGE_BASE_NAME, description="演示知识库")
    print(f"✅ 知识库创建成功，ID: {kb.kb_id}")

    print("   正在索引文档...")
    index_result = doc.index_to_knowledge_base(
        kb.kb_id, chunk_strategy="markdown_hierarchical"
    )
    print("✅ 文档索引完成")

    # 5. 搜索知识库
    print("\n[5/5] 搜索知识库...")
    query = "内容"  # 替换为你想搜索的关键词
    print(f"   搜索关键词: '{query}'")

    results = kb.search(query, top_k=3)
    print(f"✅ 找到 {len(results)} 条结果:\n")

    for i, result in enumerate(results, 1):
        print(f"   结果 {i}:")
        print(f"   - 相似度: {result.similarity_score:.3f}")
        print(f"   - 内容预览: {result.text_content[:100]}...")
        print()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)

except UnifilesError as e:
    print(f"\n❌ 错误: {e}")
    print("\n提示:")
    print("1. 请确保已启动 Unifiles 服务 (默认端口 8088)")
    print("2. 请检查 API_KEY 是否正确")
    print("3. 请确保 FILE_PATH 指向的文件存在")

except Exception as e:
    print(f"\n❌ 未预期的错误: {e}")
