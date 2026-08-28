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

During the staged migration, Python and TypeScript client cores are manifest
targets with exact legacy output allowlists. Their output roots move under
`packages/generated/` in the SDK artifact phase.
