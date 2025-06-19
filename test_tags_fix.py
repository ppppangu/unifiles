#!/usr/bin/env python3
"""
Test script to verify the tags fix
"""

import asyncio
import json
from graph_module import get_documents_graph, produce_document_graph

async def test_tags_functionality():
    """Test the tags functionality with the fix"""
    print("Testing tags functionality...")
    
    # Test with the specific IDs from the user's example
    test_user_id = "75cc796b-8f74-41c2-9735-902f7ca1b735"
    test_kb_id = "3996f442-fd2a-4a4a-952f-0745d3554b7a"
    
    print(f"User ID: {test_user_id}")
    print(f"Knowledge Base ID: {test_kb_id}")
    
    try:
        # First, try to get documents (this should show the current state)
        print("\n1. Getting current documents...")
        result = await get_documents_graph(test_user_id, test_kb_id)
        print(f"Get documents result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # If successful and documents exist, try to produce tags
        if result.get("status") == "ok" and result.get("documents"):
            print(f"\nFound {len(result['documents'])} documents")
            for doc in result["documents"]:
                print(f"  - {doc['id']}: {doc['name']} (tags: {doc['tags']})")
            
            print("\n2. Producing document graph (generating tags)...")
            produce_result = await produce_document_graph(test_user_id, test_kb_id)
            print(f"Produce result: {json.dumps(produce_result, indent=2, ensure_ascii=False)}")
            
            # Get documents again to see if tags were updated
            print("\n3. Getting documents after tag generation...")
            result_after = await get_documents_graph(test_user_id, test_kb_id)
            print(f"Get documents after result: {json.dumps(result_after, indent=2, ensure_ascii=False)}")
            
            if result_after.get("status") == "ok" and result_after.get("documents"):
                print(f"\nAfter tag generation:")
                for doc in result_after["documents"]:
                    print(f"  - {doc['id']}: {doc['name']} (tags: {doc['tags']})")
        else:
            print(f"Error or no documents found: {result}")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tags_functionality())
