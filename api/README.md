# OpenAPI contract workflow

`openapi.yaml` is the only source of truth for the HTTP protocol. Do not derive it from FastAPI and
do not edit generated code.

```text
api/openapi.yaml
├── apps/server/generated/       FastAPI routers, models and Base*Api interfaces
├── packages/python/generated/   Complete httpx Python client core
└── packages/typescript/generated/ Complete Fetch TypeScript client core
```

Handwritten code is deliberately outside those directories:

- `apps/server/src/unifiles_server/implementation/` implements generated server interfaces.
- `packages/python/src/unifiles/` adds retries, public errors and polling around the generated core.
- `packages/typescript/src/` adds retries, public errors and polling around the generated core.

After editing the contract:

```bash
uv run python scripts/generate_contract.py
uv run python scripts/check_openapi.py
uv run pytest
npm run check
```

Keep every `operationId` stable and globally unique. Regeneration may change generated method
signatures, but it never writes into handwritten implementation directories. A contract-breaking
change should therefore produce a type or test failure in the implementation that needs adapting,
not overwrite that implementation.
