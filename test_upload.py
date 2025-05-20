"""
Script to test the upload API of the file server
"""
import requests
import os
import traceback
from urllib.parse import unquote

try:
    # First check if the server is running
    health_url = "http://localhost:8000/health"
    try:
        health_response = requests.get(health_url, timeout=5)
        print(f"Server health check: {health_response.status_code} - {health_response.text}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to the server. Make sure the server is running on http://localhost:8000")
        exit(1)

    # URL of the PDF file
    pdf_url = "https://publicwyy.obs.cn-north-4.myhuaweicloud.com/DeployServive/MinerU_npu_api/v1.1/test_sample/%E5%A4%A7%E6%A8%A1%E5%9E%8B%E8%B5%8B%E8%83%BD%E4%B8%AD%E5%B0%8F%E5%AD%A6%E7%A0%94%E5%AD%A6%E4%B8%93%E9%A1%B9%E9%A1%B9%E7%9B%AE.pdf"

    # Download the PDF file
    print(f"Downloading PDF from: {unquote(pdf_url)}")
    response = requests.get(pdf_url)
    if response.status_code != 200:
        print(f"Failed to download PDF: {response.status_code}")
        exit(1)

    pdf_content = response.content
    print(f"PDF downloaded successfully, size: {len(pdf_content)} bytes")

    # Prepare the request to the upload API
    upload_url = "http://localhost:8000/upload"  # Assuming the server is running locally

    # Required form fields
    form_data = {
        "knowledge_base_id": "a4547663-66dd-42ce-94b0-6250e5abcddd",  # Replace with your actual knowledge base ID
        "document_id": "95b02bf7-cb68-4de2-ba0a-7ed173a0d386",       # Replace with your actual document ID
        "mode": ["vector"],                  # Using default mode
        "user_id": "06b9c94e-9105-41c5-9a95-aef26e257ba4"           # Providing a user ID to bypass the database lookup
    }

    # Prepare the file for upload
    filename = unquote(pdf_url.split('/')[-1])
    files = {
        "pdf_pdf_file": (filename, pdf_content, "application/pdf")
    }

    # Make the request
    print(f"Sending request to {upload_url} with knowledge_base_id={form_data['knowledge_base_id']}, document_id={form_data['document_id']}")

    # Set a longer timeout and enable debug
    response = requests.post(upload_url, data=form_data, files=files, timeout=60)

    # Print the response
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.text}")

    # If we got an error, try to get more information
    if response.status_code >= 400:
        print("Error occurred. Checking server status...")
        try:
            health_response = requests.get(health_url, timeout=5)
            print(f"Server is still running. Health check: {health_response.status_code} - {health_response.text}")
        except requests.exceptions.ConnectionError:
            print("Server appears to have crashed!")

except Exception as e:
    print(f"An error occurred during test execution: {str(e)}")
    traceback.print_exc()
