# OpenAPI contract workflow

`unifiles.yaml` is the only source of truth for the HTTP protocol. Do not derive it from FastAPI
and do not edit generated code.

```text
contracts/openapi/unifiles.yaml
├── packages/generated/server-protocol-python/ FastAPI protocol artifact
├── packages/python/generated/                 Transitional Python client core
└── packages/typescript/generated/             Transitional TypeScript client core
```

Handwritten code is deliberately outside those directories:

- `apps/server/src/unifiles_server/implementation/` implements generated server interfaces.
- `packages/python/src/unifiles/` adds retries, public errors and polling around the generated core.
- `packages/typescript/src/` adds retries, public errors and polling around the generated core.

After editing the contract:

```bash
uv run python codegen/scripts/validate_contract.py
uv run python codegen/scripts/codegen.py generate all
uv run python codegen/scripts/codegen.py check all
uv run pytest
npm run check
```

The client cores currently use manifest-owned legacy output paths and move under
`packages/generated/` in the SDK artifact migration phase.

Keep every `operationId` stable and globally unique. Regeneration may change generated method
signatures, but it never writes into handwritten implementation directories. A contract-breaking
change should therefore produce a type or test failure in the implementation that needs adapting,
not overwrite that implementation.
