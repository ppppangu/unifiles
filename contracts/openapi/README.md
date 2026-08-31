# OpenAPI contract workflow

`unifiles.yaml` is the only source of truth for the HTTP protocol. Do not derive it from FastAPI
and do not edit generated code.

```text
contracts/openapi/unifiles.yaml
├── packages/generated/server-protocol-python/ FastAPI protocol artifact
├── packages/generated/sdk-python/             Python client core artifact
└── packages/generated/sdk-typescript/         TypeScript client core artifact
```

Handwritten code is deliberately outside those directories:

- `apps/server/src/unifiles_server/modules/` implements and statically composes generated interfaces.
- `packages/python/src/unifiles/` adds retries, public errors and polling around the generated core.
- `packages/typescript/src/` adds retries, public errors and polling around the generated core.

## Public contract boundary

The generated SDKs intentionally expose the public wire contract; clients could recover that
contract from network traffic even if the server were closed source. Do not use schema secrecy as
an authorization or intellectual-property boundary. Keep persistence models, internal service
commands, private operations, stack traces, and provider details outside this contract. A closed
server should publish a sanitized public OpenAPI document and keep any internal API in a separate,
non-distributed contract. SDK errors should expose stable public codes, messages, and request IDs,
never raw framework validation exceptions.

After editing the contract:

```bash
uv run python codegen/scripts/validate_contract.py
uv run python codegen/scripts/codegen.py generate all
uv run python codegen/scripts/codegen.py check all
uv run pytest
npm run check
```

Keep every `operationId` stable and globally unique. Regeneration may change generated method
signatures, but it never writes into handwritten implementation directories. A contract-breaking
change should therefore produce a type or test failure in the implementation that needs adapting,
not overwrite that implementation.
