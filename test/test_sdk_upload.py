#!/usr/bin/env python3
"""
最小可运行示例：使用 SDK 对 test 文件夹下的 .docx 文件执行：
1) 上传
2) 内容提取
3) 创建知识库
4) 文档索引
5) 向量检索

用法：
  UNIFILES_API_KEY=sk_xxx python test/test_sdk_upload.py

可选：
  UNIFILES_API_BASE_URL=http://127.0.0.1:8088  # 默认已是 8088
"""

import os
import sys
from pathlib import Path

# 确保可以从源码导入（无需安装为包）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
from unifiles.client import Unifile  # noqa: E402


def main() -> int:
    base_url = os.getenv("UNIFILES_API_BASE_URL", "http://127.0.0.1:8088")
    api_key = os.environ.get("UNIFILES_API_KEY", "[REDACTED]")
    test_file = Path(__file__).parent / "100道简答题.docx"

    print("=" * 60)
    print("SDK 上传最小示例")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"Docx: {test_file}")

    if not api_key:
        print("\n❌ 缺少环境变量 UNIFILES_API_KEY。请设置后重试。")
        return 1

    if not test_file.exists():
        print(f"\n❌ 测试文件不存在: {test_file}")
        return 1

    try:
        client = Unifile(api_key=api_key, base_url=base_url)
        print("\n✅ 客户端初始化成功")

        # 1) 上传
        print("\n🚀 开始上传...")
        doc = client.upload_file(test_file, is_public=False)
        print("\n✅ 上传成功")
        print(f"File ID   : {doc.file_id}")
        print(f"Filename  : {doc.filename}")
        print(f"File Size : {doc.file_size} bytes")
        print(f"Status    : {doc.status.value}")

        # 2) 提取内容（第二层）
        print("\n🔍 开始内容提取 (mode=simple)...")
        extract_resp = doc.extract_content(mode="simple")
        print("✅ 提取请求返回")
        extracted = extract_resp.get("extracted_content") or {}
        extraction_id = extracted.get("extraction_id") or extracted.get("extractionId")
        print(f"Extraction ID: {extraction_id}")
        # 尝试读取提取内容预览
        try:
            content = doc.get_content()
            text_preview = (content.get("extracted_text") or "")[:120]
            md_preview = (content.get("markdown_content") or "")[:120]
            if text_preview:
                print(f"Text Preview: {text_preview}...")
            if md_preview:
                print(f"Markdown Preview: {md_preview}...")
        except Exception as e:
            print(f"⚠️ 获取提取内容预览失败（可忽略）: {e}")

        # 3) 创建知识库
        kb_name = f"SDK最小示例知识库_{int(time.time())}"
        print(f"\n📚 创建知识库: {kb_name}")
        kb = client.create_knowledge_base(kb_name, description="SDK最小示例")
        print("✅ 知识库创建成功")
        print(f"KB ID : {kb.kb_id}")
        print(f"Name  : {kb.name}")

        # 4) 文档索引（第三层）
        # 为提高成功率使用服务端默认策略 'markdown_hierarchical'
        print("\n🧩 开始索引文档到知识库 (chunk_strategy=markdown_hierarchical)...")
        index_resp = doc.index_to_knowledge_base(kb.kb_id, chunk_strategy="markdown_hierarchical")
        print("✅ 索引请求返回")
        doc_info = index_resp.get("document", {})
        print(f"Document ID  : {doc_info.get('document_id')}")
        print(f"Chunk Count  : {doc_info.get('chunk_count')}")
        print(f"Index Status : {doc_info.get('indexing_status')}")

        # 5) 向量检索
        print("\n🔎 向量检索 TopK=3 ...")
        for q in ["电气", "安装", "简答题"]:
            try:
                results = kb.search(q, top_k=3)
                print(f"\nQuery: {q} -> {len(results)} 条")
                for i, r in enumerate(results, 1):
                    preview = (r.text_content or "")[:80]
                    print(f"  #{i} score={r.similarity_score:.3f}  {preview}")
            except Exception as e:
                print(f"⚠️ 检索失败（忽略）query='{q}': {e}")

        return 0
    except Exception as e:
        print("\n❌ 过程失败")
        print(f"错误: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
