"""
Script to test the MinerUClient class directly without going through the server
"""
import asyncio
from src.mineru_client import MinerUClient
import os
from dotenv import load_dotenv, find_dotenv
import boto3

# Load environment variables
load_dotenv(find_dotenv())

async def test_mineru_client():
    # Read a sample PDF file
    try:
        with open("sample.pdf", "rb") as f:
            file_content = f.read()
            print(f"Read sample.pdf, size: {len(file_content)} bytes")
    except FileNotFoundError:
        print("sample.pdf not found, using a small dummy PDF content")
        # Use a small dummy PDF content for testing
        file_content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    
    # Initialize S3 connection
    s3_connection = boto3.client(
        's3',
        endpoint_url=os.getenv("FILE_SERVER_S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("FILE_SERVER_S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("FILE_SERVER_S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("FILE_SERVER_S3_REGION")
    )
    
    # Create MinerUClient instance
    mineru_client = MinerUClient(
        mineru_url=os.getenv("FILE_SERVER_MINERU_URL"),
        file_content=file_content,
        s3_connection=s3_connection,
        bucket_name=os.getenv("FILE_SERVER_S3_BUCKET_NAME"),
        user_id="test-user-id",
        knowledge_base_id="test-kb-id",
        document_id="test-doc-id"
    )
    
    # Test health check
    try:
        print("Testing health check...")
        await mineru_client.health()
        print("Health check passed!")
    except Exception as e:
        print(f"Health check failed: {str(e)}")
    
    # Test OCR
    try:
        print("Testing OCR...")
        result = await mineru_client.ocr()
        print(f"OCR result: {result}")
    except Exception as e:
        print(f"OCR failed: {str(e)}")
    
    # Close S3 connection
    s3_connection.close()

if __name__ == "__main__":
    asyncio.run(test_mineru_client())
