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
