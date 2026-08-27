# unifiles-client

Official synchronous and asynchronous Python SDK for Unifiles.

```bash
pip install unifiles-client
```

```python
from unifiles import UnifilesClient

client = UnifilesClient(api_key="sk_...", base_url="http://localhost:8088")
file = client.files.upload("document.pdf")
extraction = client.extractions.create(file.id).wait()
```

Use `AsyncUnifilesClient` for asyncio applications.

Endpoint calls, request models and wire serialization are generated from `api/openapi.yaml` into
`generated/unifiles_generated`. The public resource facade adds retries, typed errors and polling;
`client.raw` exposes the complete generated API surface directly.
