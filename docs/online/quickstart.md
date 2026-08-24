# 快速开始

本指南使用本机自部署 Server，分别演示 Python、TypeScript 和 CLI。

## 1. 启动 Server

```bash
git clone https://github.com/ppppangu/unifiles.git
cd unifiles
uv sync --all-packages --group dev

UNIFILES_BOOTSTRAP_API_KEY=sk_test_local \
  uv run unifiles-server --host 127.0.0.1 --port 8088
```

服务启动后可访问 `http://localhost:8088/docs`，数据默认写入 `.unifiles-data/`。

## 2. 选择客户端

=== "Python（同步）"

    ```bash
    pip install unifiles-client
    ```

    ```python
    from unifiles import UnifilesClient

    client = UnifilesClient(
        api_key="sk_test_local",
        base_url="http://localhost:8088",
    )

    file = client.files.upload("document.pdf")
    extraction = client.extractions.create(file.id).wait()

    kb = client.knowledge_bases.create("my-docs")
    document = client.knowledge_bases.documents.create(kb.id, file.id).wait()

    results = client.knowledge_bases.search(kb.id, "关键内容")
    for chunk in results.chunks:
        print(chunk.score, chunk.content)
    ```

=== "Python（异步）"

    ```python
    import asyncio
    from unifiles import AsyncUnifilesClient

    async def main():
        async with AsyncUnifilesClient(
            api_key="sk_test_local",
            base_url="http://localhost:8088",
        ) as client:
            file = await client.files.upload("document.pdf")
            extraction = await client.extractions.create(file.id)
            await extraction.wait()

    asyncio.run(main())
    ```

=== "TypeScript"

    ```bash
    npm install @wyy/unifiles
    ```

    ```typescript
    import { UnifilesClient } from "@wyy/unifiles";

    const client = new UnifilesClient({
      apiKey: "sk_test_local",
      baseUrl: "http://localhost:8088",
    });

    const file = await client.files.upload("document.pdf");
    const extraction = await client.extractions.create(file.id);
    await extraction.wait();

    const kb = await client.knowledgeBases.create("my-docs");
    const document = await client.knowledgeBases.documents.create(kb.id, file.id);
    await document.wait();

    const results = await client.knowledgeBases.search(kb.id, "关键内容");
    ```

=== "CLI"

    ```bash
    npm install -g @wyy/unifiles-cli
    printf '%s' sk_test_local | unifiles config set local \
      --base-url http://localhost:8088 \
      --api-key-stdin

    file_id=$(unifiles --profile local --output json files upload document.pdf | jq -r .id)
    extraction_id=$(unifiles --profile local --output json extractions create "$file_id" --wait | jq -r .id)
    unifiles --profile local kb list | jq .
    ```

## 支持范围

内置单机 Server 可直接提取文本和包含文本层的 PDF。图片、扫描件、无文本层 PDF 和
`advanced` 模式通过 `UNIFILES_OCR_ENDPOINT` 接入远程 OCR Provider；未配置时返回明确的
`EXTRACTION_FAILED`，不会返回模拟内容。
