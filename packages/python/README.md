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
