# Contributing

Unifiles is a Python and Node.js monorepo.

```bash
uv sync --all-packages --group dev --group docs
npm ci
uv run pytest
npm run check
uv run mkdocs build --strict
```

Protocol changes start in `contracts/openapi/unifiles.yaml`, the only protocol source of truth. Regenerate the
FastAPI bindings and both full SDK cores with:

```bash
npm run generate
npm run generate:check
```

Never edit a target below `packages/generated/`. Each leaf is owned by one manifest target and can
be deleted and rebuilt independently. Handwritten feature modules, SDK facades and the product CLI
live outside that tree, so regeneration cannot overwrite them. Keep OCR, chunking, authorization,
quotas and persistence in the handwritten Server modules.

Package tags publish coupled generated and handwritten artifacts in dependency order. See
[`RELEASING.md`](RELEASING.md) before creating a release tag.
