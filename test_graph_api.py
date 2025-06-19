#!/usr/bin/env python3
"""
Test script for debugging graph module API issues
"""

import asyncio
import asyncpg
from graph_module import get_documents_graph, produce_document_graph
from src.tools import read_pg_config

async def test_database_connection():
    """Test basic database connection and schema"""
    pg_config = read_pg_config()
    print(f"Connecting to database: {pg_config['host']}:{pg_config['port']}")
    
    try:
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )
        
        # Test basic connection
        result = await conn.fetchval("SELECT version()")
        print(f"Database version: {result}")
        
        # Check if schema exists
        schema_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'chunk_schema')"
        )
        print(f"chunk_schema exists: {schema_exists}")
        
        # Check tables
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'chunk_schema'"
        )
        print(f"Tables in chunk_schema: {[t['table_name'] for t in tables]}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

async def test_user_knowledge_base_data():
    """Test what data exists for users and knowledge bases"""
    pg_config = read_pg_config()
    
    try:
        conn = await asyncpg.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            user=pg_config["user"],
            password=pg_config["password"],
            database=pg_config["database"]
        )
        
        # Check users table
        users = await conn.fetch("SELECT id FROM chunk_schema.users LIMIT 10")
        print(f"Sample users: {[u['id'] for u in users]}")
        
        # Check knowledge bases
        kbs = await conn.fetch("SELECT id, user_id FROM chunk_schema.knowledge_bases LIMIT 10")
        print(f"Sample knowledge bases: {[(kb['id'], kb['user_id']) for kb in kbs]}")
        
        # Check documents
        docs = await conn.fetch("SELECT id, knowledge_base_id FROM chunk_schema.documents LIMIT 10")
        print(f"Sample documents: {[(doc['id'], doc['knowledge_base_id']) for doc in docs]}")
        
        # Test specific knowledge base from the user's example
        test_kb_id = "3996f442-fd2a-4a4a-952f-0745d3554b7a"
        test_user_id = "75cc796b-8f74-41c2-9735-902f7ca1b735"
        
        print(f"\nTesting specific IDs from user's example:")
        print(f"User ID: {test_user_id}")
        print(f"Knowledge Base ID: {test_kb_id}")
        
        # Check if user exists
        user_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.users WHERE id = $1)", test_user_id
        )
        print(f"User exists: {user_exists}")
        
        # Check if knowledge base exists
        kb_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.knowledge_bases WHERE id = $1)", test_kb_id
        )
        print(f"Knowledge base exists: {kb_exists}")
        
        # Check if knowledge base belongs to user
        kb_user_match = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.knowledge_bases WHERE id = $1 AND user_id = $2)",
            test_kb_id, test_user_id
        )
        print(f"Knowledge base belongs to user: {kb_user_match}")
        
        # Check documents in this knowledge base
        docs_in_kb = await conn.fetch(
            "SELECT id, name, tags FROM chunk_schema.documents WHERE knowledge_base_id = $1",
            test_kb_id
        )
        print(f"Documents in knowledge base {test_kb_id}: {len(docs_in_kb)}")
        for doc in docs_in_kb:
            print(f"  - {doc['id']}: {doc['name']} (tags: {doc['tags']})")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error testing data: {e}")

async def test_get_documents_graph():
    """Test the get_documents_graph function directly"""
    test_user_id = "75cc796b-8f74-41c2-9735-902f7ca1b735"
    test_kb_id = "3996f442-fd2a-4a4a-952f-0745d3554b7a"
    
    print(f"\nTesting get_documents_graph function:")
    print(f"User ID: {test_user_id}")
    print(f"Knowledge Base ID: {test_kb_id}")
    
    try:
        result = await get_documents_graph(test_user_id, test_kb_id)
        print(f"Result: {result}")
        
        if result.get("status") == "ok":
            documents = result.get("documents", [])
            print(f"Number of documents returned: {len(documents)}")
            for doc in documents:
                print(f"  - {doc}")
        
    except Exception as e:
        print(f"Error calling get_documents_graph: {e}")

async def main():
    print("=== Graph Module API Debug Test ===\n")
    
    # Test 1: Database connection
    print("1. Testing database connection...")
    if not await test_database_connection():
        print("Database connection failed. Exiting.")
        return
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Check data
    print("2. Testing user and knowledge base data...")
    await test_user_knowledge_base_data()
    
    print("\n" + "="*50 + "\n")
    
    # Test 3: Test function
    print("3. Testing get_documents_graph function...")
    await test_get_documents_graph()

if __name__ == "__main__":
    asyncio.run(main())
