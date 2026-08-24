# Contributing

Unifiles is a Python and Node.js monorepo.

```bash
uv sync --all-packages --group dev --group docs
npm ci
uv run pytest
npm run check
uv run mkdocs build --strict
```

Protocol changes must update `api/openapi.yaml` and regenerate both private wire model sets:

```bash
uv run python scripts/export_openapi.py
uv run python scripts/generate_contract.py
```

Do not edit generated files directly. Keep OCR, chunking, authorization, quotas and persistence in
the Server; SDKs and CLI remain typed transport layers.
