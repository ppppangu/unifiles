#!/usr/bin/env python3
"""
Debug script to test tags issue and write results to file
"""

import asyncio
import asyncpg
import sys
import traceback
from src.tools import read_pg_config

async def debug_tags():
    """Debug tags issue and write results to file"""
    output = []

    try:
        # Use the proper database configuration
        pg_config = read_pg_config()
        output.append(f"Using database config: {pg_config['host']}:{pg_config['port']}")

        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )
        
        output.append("Connected to database successfully")
        
        # Test specific knowledge base from the user's example
        test_kb_id = "3996f442-fd2a-4a4a-952f-0745d3554b7a"
        test_user_id = "75cc796b-8f74-41c2-9735-902f7ca1b735"
        
        output.append(f"Testing Knowledge Base ID: {test_kb_id}")
        output.append(f"Testing User ID: {test_user_id}")
        
        # Check if the knowledge base exists
        kb_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.knowledge_bases WHERE id = $1)",
            test_kb_id
        )
        output.append(f"Knowledge base exists: {kb_exists}")
        
        # Check documents in this knowledge base with their tags
        docs_in_kb = await conn.fetch(
            "SELECT id, name, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
            test_kb_id
        )
        output.append(f"Found {len(docs_in_kb)} documents in knowledge base")
        
        for i, doc in enumerate(docs_in_kb):
            output.append(f"Document {i+1}:")
            output.append(f"  ID: {doc['id']}")
            output.append(f"  Name: {doc['name']}")
            output.append(f"  Tags: {doc['tags']}")
            output.append(f"  Tags type: {type(doc['tags'])}")
            output.append(f"  Tags length: {len(doc['tags']) if doc['tags'] else 0}")
            output.append("")
        
        # Test a simple update and read back
        if docs_in_kb:
            test_doc_id = docs_in_kb[0]['id']
            output.append(f"Testing update/read cycle with document: {test_doc_id}")
            
            # Update with test tags
            test_tags = ["test_tag_1", "test_tag_2"]
            await conn.execute(
                "UPDATE chunk_schema.documents SET tags = $1 WHERE id = $2",
                test_tags,
                test_doc_id
            )
            output.append(f"Updated document with test tags: {test_tags}")
            
            # Read back immediately
            result = await conn.fetchrow(
                "SELECT tags FROM chunk_schema.documents WHERE id = $1",
                test_doc_id
            )
            output.append(f"Read back tags: {result['tags']}")
            output.append(f"Read back tags type: {type(result['tags'])}")
        
        await conn.close()
        
    except Exception as e:
        output.append(f"Error: {e}")
        output.append(traceback.format_exc())
    
    # Write output to file
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        for line in output:
            f.write(line + "\n")
    
    print("Debug completed. Check debug_output.txt for results.")

if __name__ == "__main__":
    asyncio.run(debug_tags())
