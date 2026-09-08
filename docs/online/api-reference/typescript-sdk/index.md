# TypeScript SDK

`@wyy/unifiles` 是面向 Node.js 22+ 的官方 SDK，同时发布 ESM、CommonJS 和类型声明。

```bash
npm install @wyy/unifiles
```

```typescript
import { UnifilesClient } from "@wyy/unifiles";

const client = new UnifilesClient({
  apiKey: process.env.UNIFILES_API_KEY,
  baseUrl: process.env.UNIFILES_BASE_URL,
  timeoutMs: 30_000,
  maxRetries: 3,
});
```

`baseUrl` 填服务地址即可，SDK 会自动补上 `/v1`。

## 命名空间

```typescript
client.files
client.extractions
client.knowledgeBases
client.knowledgeBases.documents
client.webhooks
client.apiKeys
client.usage
client.system
```

TypeScript 公开字段使用 camelCase；REST JSON 的 snake_case 由 SDK 转换。

## 文件、提取与知识库

```typescript
const file = await client.files.upload("contract.pdf", {
  metadata: { department: "legal" },
  tags: ["contract"],
});

const extraction = await client.extractions.create(file.id, { mode: "normal" });
await extraction.wait({ timeoutMs: 300_000, pollIntervalMs: 2_000 });

const kb = await client.knowledgeBases.create("contracts", {
  chunkingStrategy: { type: "semantic", chunkSize: 512, overlap: 50 },
});

const indexedDocument = await client.knowledgeBases.documents.create(kb.id, file.id);
await indexedDocument.wait();

const results = await client.knowledgeBases.hybridSearch(kb.id, "违约责任", {
  vectorWeight: 0.7,
  keywordWeight: 0.3,
  topK: 5,
});

const health = await client.system.health();
const liveness = await client.system.liveness();
const details = await client.system.details();
```

## 错误

```typescript
import { NotFoundError, RateLimitError } from "@wyy/unifiles";

try {
  await client.files.get("missing");
} catch (error) {
  if (error instanceof NotFoundError) console.error(error.requestId);
  if (error instanceof RateLimitError) console.error(error.retryAfter);
}
```

该 SDK 只面向可信的 Node.js 服务端环境。不要把 Secret API Key 放进浏览器代码。

`client.raw` 提供完整的 generated OpenAPI surface，适合低层协议调用；常规应用
优先使用 public facade。
