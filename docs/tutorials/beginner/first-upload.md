# Tutorial: Your First File Upload

本教程将指导您完成第一个文件上传到 Unifiles 的完整流程。

## 学习目标

完成本教程后，您将学会：

- 注册 Unifiles 用户并获取 API Key
- 使用 API 上传文件
- 查看文件元数据
- 下载文件

## 前置要求

- Unifiles 服务已安装并运行（参见 [安装指南](../../getting-started/installation.md)）
- 一个 PDF 文件用于测试

## 步骤 1：注册用户

首先注册一个 Unifiles 用户并获取 API Key：

```bash
curl -X POST http://localhost:8088/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

**响应示例**：

```json
{
  "success": true,
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "testuser",
    "api_key": "[REDACTED]",
    "created_at": "2025-01-04T10:00:00Z"
  },
  "message": "User registered successfully"
}
```

**重要**：请保存您的 `api_key`，后续步骤会用到！

## 步骤 2：上传文件

现在使用获取的 API Key 上传一个 PDF 文件：

```bash
curl -X POST http://localhost:8088/api/v1/files \
  -H "Authorization: Bearer [REDACTED]" \
  -F "file=@/path/to/your/document.pdf"
```

**使用 Python**：

```python
import requests

api_key = "[REDACTED]"
headers = {"Authorization": f"Bearer {api_key}"}

with open("document.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(
        "http://localhost:8088/api/v1/files",
        headers=headers,
        files=files
    )

print(response.json())
```

**响应示例**：

```json
{
  "success": true,
  "data": {
    "file_id": "660e8400-e29b-41d4-a716-446655440000",
    "filename": "document.pdf",
    "file_size": 1024000,
    "content_type": "application/pdf",
    "status": "uploaded",
    "created_at": "2025-01-04T10:05:00Z",
    "download_url": "/api/v1/files/660e8400-e29b-41d4-a716-446655440000/download"
  },
  "message": "File uploaded successfully"
}
```

**记下** `file_id`，下一步会用到！

## 步骤 3：查看文件元数据

查看刚上传文件的详细信息：

```bash
curl http://localhost:8088/api/v1/files/660e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer [REDACTED]"
```

**响应示例**：

```json
{
  "success": true,
  "data": {
    "file_id": "660e8400-e29b-41d4-a716-446655440000",
    "filename": "document.pdf",
    "file_size": 1024000,
    "content_type": "application/pdf",
    "status": "uploaded",
    "file_path": "s3://unifiles/users/550e8400.../files/660e8400....pdf",
    "created_at": "2025-01-04T10:05:00Z",
    "updated_at": "2025-01-04T10:05:00Z"
  }
}
```

## 步骤 4：下载文件

使用 download URL 下载文件：

```bash
curl -o downloaded.pdf \
  http://localhost:8088/api/v1/files/660e8400-e29b-41d4-a716-446655440000/download \
  -H "Authorization: Bearer [REDACTED]"
```

**使用 Python**：

```python
response = requests.get(
    f"http://localhost:8088/api/v1/files/{file_id}/download",
    headers=headers
)

with open("downloaded.pdf", "wb") as f:
    f.write(response.content)

print("File downloaded successfully!")
```

## 恭喜！

您已成功完成第一个文件上传！🎉

## 下一步

- [内容提取教程](content-extraction.md) - 学习如何从文件中提取内容
- [知识库教程](knowledge-base-basics.md) - 创建您的第一个知识库
- [API 参考](../../api/reference.md) - 查看更多 API 端点

## 常见问题

**Q: 上传失败，返回 401 错误**
A: 检查您的 API Key 是否正确，确保在 `Authorization` Header 中使用 `Bearer` 前缀。

**Q: 支持哪些文件格式？**
A: 目前支持 PDF、Word (docx)、PowerPoint (pptx)、Excel (xlsx)、图片 (jpg, png) 等格式。

**Q: 文件大小有限制吗？**
A: 默认限制为 100MB，可以在配置中调整。

**Q: 如何删除文件？**
A: 使用 `DELETE /api/v1/files/{file_id}` 端点删除文件。

## 完整示例代码

### Python 完整脚本

```python
#!/usr/bin/env python3
"""
Unifiles First Upload Tutorial
完整的文件上传、查看、下载示例
"""

import requests
import json

BASE_URL = "http://localhost:8088/api/v1"

def register_user():
    """注册用户并获取 API Key"""
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePassword123!"
        }
    )
    data = response.json()
    if data["success"]:
        return data["data"]["api_key"]
    else:
        raise Exception(f"Registration failed: {data['message']}")

def upload_file(api_key, file_path):
    """上传文件"""
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(
            f"{BASE_URL}/files",
            headers=headers,
            files=files
        )
    data = response.json()
    if data["success"]:
        return data["data"]["file_id"]
    else:
        raise Exception(f"Upload failed: {data['message']}")

def get_file_info(api_key, file_id):
    """获取文件信息"""
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        f"{BASE_URL}/files/{file_id}",
        headers=headers
    )
    return response.json()["data"]

def download_file(api_key, file_id, output_path):
    """下载文件"""
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        f"{BASE_URL}/files/{file_id}/download",
        headers=headers
    )
    with open(output_path, "wb") as f:
        f.write(response.content)

def main():
    # 1. 注册用户
    print("Step 1: Registering user...")
    api_key = register_user()
    print(f"API Key: {api_key}\n")

    # 2. 上传文件
    print("Step 2: Uploading file...")
    file_id = upload_file(api_key, "document.pdf")
    print(f"File ID: {file_id}\n")

    # 3. 获取文件信息
    print("Step 3: Getting file info...")
    file_info = get_file_info(api_key, file_id)
    print(json.dumps(file_info, indent=2))
    print()

    # 4. 下载文件
    print("Step 4: Downloading file...")
    download_file(api_key, file_id, "downloaded.pdf")
    print("File downloaded successfully!\n")

    print("✅ Tutorial completed!")

if __name__ == "__main__":
    main()
```

### JavaScript 完整脚本

```javascript
// Unifiles First Upload Tutorial (Node.js)

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const BASE_URL = 'http://localhost:8088/api/v1';

async function registerUser() {
  const response = await axios.post(`${BASE_URL}/auth/register`, {
    username: 'testuser',
    email: 'test@example.com',
    password: 'SecurePassword123!'
  });
  return response.data.data.api_key;
}

async function uploadFile(apiKey, filePath) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));

  const response = await axios.post(`${BASE_URL}/files`, form, {
    headers: {
      ...form.getHeaders(),
      'Authorization': `Bearer ${apiKey}`
    }
  });
  return response.data.data.file_id;
}

async function getFileInfo(apiKey, fileId) {
  const response = await axios.get(`${BASE_URL}/files/${fileId}`, {
    headers: { 'Authorization': `Bearer ${apiKey}` }
  });
  return response.data.data;
}

async function downloadFile(apiKey, fileId, outputPath) {
  const response = await axios.get(`${BASE_URL}/files/${fileId}/download`, {
    headers: { 'Authorization': `Bearer ${apiKey}` },
    responseType: 'stream'
  });

  const writer = fs.createWriteStream(outputPath);
  response.data.pipe(writer);

  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

async function main() {
  try {
    // 1. Register user
    console.log('Step 1: Registering user...');
    const apiKey = await registerUser();
    console.log(`API Key: ${apiKey}\n`);

    // 2. Upload file
    console.log('Step 2: Uploading file...');
    const fileId = await uploadFile(apiKey, 'document.pdf');
    console.log(`File ID: ${fileId}\n`);

    // 3. Get file info
    console.log('Step 3: Getting file info...');
    const fileInfo = await getFileInfo(apiKey, fileId);
    console.log(JSON.stringify(fileInfo, null, 2));
    console.log();

    // 4. Download file
    console.log('Step 4: Downloading file...');
    await downloadFile(apiKey, fileId, 'downloaded.pdf');
    console.log('File downloaded successfully!\n');

    console.log('✅ Tutorial completed!');
  } catch (error) {
    console.error('Error:', error.message);
  }
}

main();
```
