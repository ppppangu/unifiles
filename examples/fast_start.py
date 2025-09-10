"""
API使用示例 (同步版本)
演示如何使用统一客户端连接服务
"""

import time

from file_server_core.client import FileClient, Document


def cloud_example():
    """API使用示例（同步版本）"""
    print("=== API使用示例 (同步版本) ===\n")
    
    # 1. 初始化客户端
    client = FileClient(api_key="your_cloud_api_key_here", base_url="http://localhost:8087")
    print("✅ 客户端初始化完成")
    
    # 2. 创建知识库
    knowledge_base = client.create_knowledge_base(
        name="我的云端知识库",
        description="存储在云端的重要文档"
    )
    print(f"✅ 知识库创建成功: {knowledge_base.name} (ID: {knowledge_base.id})")
    
    # 3. 获取知识库列表
    kb_list = client.list_knowledge_bases()
    print(f"✅ 获取到 {len(kb_list)} 个知识库:")
    for kb in kb_list:
        print(f"   - {kb.name} (文档数: {kb.document_count})")
    
    # 4. 删除知识库（已注释）
    # client.delete_knowledge_base("old_kb_id")
    
    # 5. 上传文档
    example_kb = kb_list[0]
    document = example_kb.upload_document(file_path="/path/to/your/document.pdf")
    print(f"✅ 文档上传成功: {document.filename} (ID: {document.id})")
    print(f"   状态: {document.status.value}")
    
    # 6. 等待10秒（模拟文档处理时间）   
    print("⏳ 等待文档处理完成...")
    time.sleep(10)
    
    # 7. 重新获取知识库中的文档列表
    updated_doc_list = example_kb.list_documents()
    print("✅ 文档处理完成，知识库中的文档列表:")
    for doc in updated_doc_list:
        print(f"   - {doc.filename} (ID: {doc.id}, 状态: {doc.status.value})")
    
    # 8. 用文档ID初始化文档实例
    doc_instance = Document(client, document.id)
    print(f"✅ 文档实例初始化完成 (ID: {document.id})")
    
    # 9. 获取文档内容
    content = doc_instance.get_content()
    print("✅ 文档内容获取成功。")


if __name__ == "__main__":
    cloud_example()
