#!/usr/bin/env python3
"""
Simple test script to debug tags issue
"""

import asyncio
import asyncpg
import sys

async def test_tags():
    """Test tags directly from database"""
    try:
        # Database connection details from memory
        conn = await asyncpg.connect(
            host="192.168.132.149",
            port=5437,
            user="postgres",
            password="postgres",
            database="postgres"
        )

        print("Connected to database successfully", flush=True)

        # Test specific knowledge base from the user's example
        test_kb_id = "3996f442-fd2a-4a4a-952f-0745d3554b7a"
        test_user_id = "75cc796b-8f74-41c2-9735-902f7ca1b735"

        print(f"Testing Knowledge Base ID: {test_kb_id}", flush=True)
        print(f"Testing User ID: {test_user_id}", flush=True)

        # First, let's test if we can find any documents at all
        all_docs = await conn.fetch("SELECT id, name, tags FROM chunk_schema.documents LIMIT 5")
        print(f"Sample documents from database: {len(all_docs)}", flush=True)
        for doc in all_docs:
            print(f"  - {doc['id']}: {doc['name']} (tags: {doc['tags']})", flush=True)

        # Check documents in this knowledge base with their tags
        docs_in_kb = await conn.fetch(
            "SELECT id, name, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
            test_kb_id
        )
        print(f"Found {len(docs_in_kb)} documents in knowledge base", flush=True)

        for i, doc in enumerate(docs_in_kb):
            print(f"Document {i+1}:", flush=True)
            print(f"  ID: {doc['id']}", flush=True)
            print(f"  Name: {doc['name']}", flush=True)
            print(f"  Tags: {doc['tags']}", flush=True)
            print(f"  Tags type: {type(doc['tags'])}", flush=True)
            print(f"  Tags length: {len(doc['tags']) if doc['tags'] else 0}", flush=True)
            print(flush=True)

        # Test a simple update and read back
        if docs_in_kb:
            test_doc_id = docs_in_kb[0]['id']
            print(f"Testing update/read cycle with document: {test_doc_id}", flush=True)

            # Update with test tags
            test_tags = ["test_tag_1", "test_tag_2"]
            await conn.execute(
                "UPDATE chunk_schema.documents SET tags = $1 WHERE id = $2",
                test_tags,
                test_doc_id
            )
            print(f"Updated document with test tags: {test_tags}", flush=True)

            # Read back immediately
            result = await conn.fetchrow(
                "SELECT tags FROM chunk_schema.documents WHERE id = $1",
                test_doc_id
            )
            print(f"Read back tags: {result['tags']}", flush=True)
            print(f"Read back tags type: {type(result['tags'])}", flush=True)

        await conn.close()

    except Exception as e:
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tags())
