#!/usr/bin/env python3
"""
Simple test script for the upload_minio endpoint
"""
import requests
import io

def test_upload():
    # Create a simple test file
    test_content = b"This is a test file content for MinIO upload"
    test_filename = "test_file.txt"
    
    # Prepare the upload request
    url = "http://localhost:8000/upload_minio"
    
    # Create form data
    files = {
        'upload_file': (test_filename, io.BytesIO(test_content), 'text/plain')
    }
    
    data = {
        'user_id': 'test_user_123'
    }
    
    try:
        print(f"Testing upload to {url}")
        print(f"File: {test_filename}, Size: {len(test_content)} bytes")
        
        response = requests.post(url, files=files, data=data, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print("✅ Upload test successful!")
                print(f"File ID: {result['data']['file_id']}")
                print(f"Public URL: {result['data']['public_url']}")
            else:
                print("❌ Upload failed:", result.get('message'))
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_upload()
