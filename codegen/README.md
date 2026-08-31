# OpenAPI code generation

`contracts/openapi/unifiles.yaml` is the canonical API contract. `manifest.yaml`
declares every generated artifact and its exclusive output root.

```bash
uv run python codegen/scripts/codegen.py list
uv run python codegen/scripts/codegen.py validate
uv run python codegen/scripts/codegen.py generate all
uv run python codegen/scripts/codegen.py check all
```

If an explicitly registered Python workspace artifact has been deleted, bootstrap
generation without loading the incomplete workspace:

```bash
uv run --no-project --with pyyaml python codegen/scripts/codegen.py generate all
```

Generation always occurs below `.codegen-work/`. A target is validated and
post-processed before its manifest-owned destination is replaced. Existing
destinations require a matching `.codegen-target.json`; arbitrary output paths
are not accepted.

Every target owns exactly one direct child of `packages/generated/`:

- `server-protocol-python`: independently buildable FastAPI protocol wheel;
- `sdk-python`: independently buildable generated Python client wheel;
- `sdk-typescript`: independently buildable and packable TypeScript client package.

Package-local `dist/`, `build/`, `node_modules/` and cache directories are build
outputs rather than generated source, so drift comparison ignores them. The
target's source, package metadata, marker and generator metadata remain strict.

The Python SDK postprocessor also applies version-pinned transport customizations:
explicit multipart MIME tuples and fail-closed success-response parsing. Each
customization requires an exact generated-source match, so a generator upgrade
fails regeneration instead of silently dropping either boundary.
