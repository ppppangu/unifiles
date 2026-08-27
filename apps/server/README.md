# unifiles-server

Self-hosted implementation of the Unifiles `/v1` API.

```bash
pip install unifiles-server
UNIFILES_BOOTSTRAP_API_KEY='replace-me' unifiles-server --port 8088
```

Metadata and files are persisted under `UNIFILES_DATA_DIR` (default `.unifiles-data`).
Use `GET /health` for health checks and `/docs` for interactive OpenAPI documentation.

FastAPI routers, request/response models and base API interfaces are generated from the canonical
`api/openapi.yaml` contract under `generated/`. Business logic lives in
`src/unifiles_server/implementation/` and is never overwritten by regeneration.
