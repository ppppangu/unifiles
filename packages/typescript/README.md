# @wyy/unifiles

Official Node.js SDK for Unifiles.

```bash
npm install @wyy/unifiles
```

```typescript
import { UnifilesClient } from "@wyy/unifiles";

const client = new UnifilesClient({ apiKey: "<api-key>", baseUrl: "http://localhost:8088" });
const file = await client.files.upload("document.pdf");
const extraction = await client.extractions.create(file.id);
await extraction.wait();
const health = await client.system.health();
```

Endpoint calls, models and JSON conversion are generated from
`contracts/openapi/unifiles.yaml` under `packages/generated/sdk-typescript/src`. The generated
workspace package is an independently buildable OpenAPI projection consumed by the public SDK as
an exact package dependency. The public facade adds retries, typed errors and polling;
The public facade exposes stable resource names such as `files`, `extractions`,
`knowledgeBases`, `system`, and `usage`. `client.raw` is the advanced generated
protocol surface: its method signatures follow OpenAPI. The public facade adds
retries, typed errors and polling; use `raw` when you need an operation before it
has a higher-level helper.
