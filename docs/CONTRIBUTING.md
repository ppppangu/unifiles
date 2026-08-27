# Contributing

Unifiles is a Python and Node.js monorepo.

```bash
uv sync --all-packages --group dev --group docs
npm ci
uv run pytest
npm run check
uv run mkdocs build --strict
```

Protocol changes start in `api/openapi.yaml`, the only protocol source of truth. Regenerate the
FastAPI bindings and both full SDK cores with:

```bash
uv run python scripts/generate_contract.py
```

Never edit `apps/server/generated`, `packages/python/generated`, or
`packages/typescript/generated`. Handwritten server handlers and SDK extensions live outside those
directories, so regeneration cannot overwrite them. Keep OCR, chunking, authorization, quotas and
persistence in the handwritten Server implementation.
