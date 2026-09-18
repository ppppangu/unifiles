# unifiles-client

Official synchronous and asynchronous Python SDK for Unifiles.

```bash
pip install unifiles-client
```

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="<api-key>", base_url="http://localhost:8088")
file = client.files.upload("document.pdf")
extraction = client.extractions.create(file.id).wait()
health = client.system.health()
```

Use `AsyncUnifilesClient` for asyncio applications.

Endpoint calls, request models and wire serialization are generated from
`contracts/openapi/unifiles.yaml` into
`packages/generated/sdk-python/unifiles_generated` and installed as the separate
`unifiles-generated` dependency. The public resource facade adds retries, typed errors and polling;
The public facade exposes stable resource names such as `files`, `extractions`,
`knowledge_bases`, `system`, and `usage`. `client.raw` is the advanced generated
protocol surface: its method signatures follow OpenAPI and Python callers receive
generated exceptions instead of the public typed errors. The public wheel never embeds
the generated package.
