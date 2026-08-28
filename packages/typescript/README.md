# @wyy/unifiles

Official Node.js SDK for Unifiles.

```bash
npm install @wyy/unifiles
```

```typescript
import { UnifilesClient } from "@wyy/unifiles";

const client = new UnifilesClient({ apiKey: "sk_...", baseUrl: "http://localhost:8088" });
const file = await client.files.upload("document.pdf");
const extraction = await client.extractions.create(file.id);
await extraction.wait();
```

Endpoint calls, models and JSON conversion are generated from
`contracts/openapi/unifiles.yaml` under
`generated/src`. The public facade adds retries, typed errors and polling; `client.raw` exposes the
complete generated API surface directly.
