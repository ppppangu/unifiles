# Unifiles

Unifiles is self-hosted document infrastructure for AI applications. It separates source
file storage, content extraction, and knowledge-base indexing into composable resources
exposed through one `/v1` API.

## Packages

| Artifact | Package | Purpose |
|---|---|---|
| Server | `unifiles-server` | Self-hosted FastAPI service |
| Python SDK | `unifiles-client` | Sync and async Python clients |
| TypeScript SDK | `@wyy/unifiles` | Node.js client |
| CLI | `@wyy/unifiles-cli` | Unix-style remote API client |

## Start a local server

```bash
uv sync --all-packages --group dev
UNIFILES_BOOTSTRAP_API_KEY=sk_test_local \
  uv run unifiles-server --host 127.0.0.1 --port 8088
```

The single-node server persists metadata in SQLite and file content below
`.unifiles-data/`. Set `UNIFILES_DATA_DIR` to move that directory.

## Python

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
results = client.knowledge_bases.search(kb.id, "important terms")
```

For asynchronous applications, use `AsyncUnifilesClient` and await resource methods.

## TypeScript

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
const extraction = await (await client.extractions.create(file.id)).wait();
const kb = await client.knowledgeBases.create("my-docs");
const document = await (await client.knowledgeBases.documents.create(kb.id, file.id)).wait();
const results = await client.knowledgeBases.search(kb.id, "important terms");
```

## CLI

```bash
npm install -g @wyy/unifiles-cli
printf '%s' 'sk_test_local' | unifiles config set local \
  --base-url http://localhost:8088 \
  --api-key-stdin
unifiles --profile local files list
```

The CLI writes human-readable tables to a TTY and JSONL to a pipe. Use
`--output table|json|jsonl|raw` to choose explicitly.

## Development

```bash
uv run pytest
uv run ruff check apps packages/python scripts codegen/scripts
uv run mypy apps/server/src packages/python/src scripts codegen/scripts
npm run check
uv run python codegen/scripts/codegen.py validate
uv run python codegen/scripts/codegen.py check all
```

[`contracts/openapi/unifiles.yaml`](contracts/openapi/unifiles.yaml) is the hand-maintained source of truth. It generates
the FastAPI protocol layer and both official SDK cores. After a contract change run:

```bash
npm run contract:validate
npm run generate
npm run generate:check
```

Generated directories are replaceable artifacts; server implementations and SDK extensions live
outside them and are never overwritten. See [`contracts/openapi/README.md`](contracts/openapi/README.md) for the maintenance
workflow and directory boundaries.

The three generated package roots are `server-protocol-python`, `sdk-python`, and `sdk-typescript`
under [`packages/generated`](packages/generated). They are independently rebuildable distribution
dependencies; the product CLI remains handwritten under [`apps/cli`](apps/cli).

See [unifiles.dev](https://unifiles.dev) for full documentation.
