# Releasing UniFiles packages

Release tags are the only supported publication entry point. The workflow validates that the tag
version matches every package it will publish, each public package's exact generated dependency,
and npm trusted-publishing repository identity before any upload begins.

| Tag | Published artifacts, in dependency order |
|---|---|
| `python-vX.Y.Z` | `unifiles-generated`, then `unifiles-client` |
| `server-vX.Y.Z` | `unifiles-server-protocol`, then `unifiles-server` |
| `typescript-vX.Y.Z` | `@wyy/unifiles-generated`, then `@wyy/unifiles` |
| `cli-vX.Y.Z` | `@wyy/unifiles-cli` |

The generated core and its public consumer intentionally use the same version while they have exact
package dependencies. Change both version fields in one pull request, regenerate all targets, and
run the complete checks before tagging:

```bash
uv sync --all-packages --group dev --group docs
npm ci
uv run python codegen/scripts/codegen.py check all
uv run pytest
npm run check
uv run --group docs mkdocs build --strict
```

Verify the intended tag locally, for example:

```bash
uv run python scripts/check_release_versions.py --tag python-v0.1.0
```

Do not upload only a public package when its generated dependency version is new. Do not publish
files from `packages/generated/` by hand: the release workflow builds the committed, drift-checked
artifact and publishes it before its consumer. npm publication uses Node.js 24 and npm 11.5.1 so
GitHub OIDC trusted publishing is available.

Before the first tag, configure a Trusted Publisher for every PyPI and npm package named in the
table. Each publisher must point to the `ppppangu/unifiles` repository, workflow filename
`release.yml` (the file is located at `.github/workflows/release.yml`), and the matching `pypi` or
`npm` GitHub environment. npm also checks the committed package `repository.url`; the release
version check rejects a mismatch before publish.
