# Releasing UniFiles packages

## Documentation site

`.github/workflows/docs.yml` is the documentation build check: it runs `mkdocs build --strict` and
uploads the generated `site` directory as an artifact. The public site is published by Cloudflare
Pages project `unifiles-docs`.

The current Cloudflare Pages configuration is:

| Setting | Value |
|---|---|
| Git repository | `ppppangu/unifiles` |
| Production branch | `main` |
| Root directory | `/` |
| Build command | `python3 -m pip install -r requirements-docs.txt && python3 -m mkdocs build --strict` |
| Output directory | `site` |
| Custom domains | `unifiles.dev`, `www.unifiles.dev` |
| Automatic deployment | enabled |
| Build variable (Production and Preview) | `SKIP_DEPENDENCY_INSTALL=1` |
| Python version | read from `.python-version` |

Keep `SKIP_DEPENDENCY_INSTALL=1` in both environments. Without it, Pages detects the root
`pyproject.toml` and attempts `pip install .` before the build command. This repository root is
a uv workspace, not an installable Python distribution, so that automatic step fails with
`Multiple top-level packages discovered`. The explicit build command installs only the document
dependencies in `requirements-docs.txt`; GitHub Actions uses the same file and Python version.

A push to `main` now follows this path:

```text
GitHub push → GitHub Actions docs check
           └→ Cloudflare Pages build → site/ → unifiles.dev
```

After a documentation push, verify the deployment without changing it:

```bash
npx --yes wrangler pages deployment list --project-name unifiles-docs
```

The latest Production deployment must show the intended commit and finish successfully.
Wrangler's `Active` can mean queued or building; it is not proof of publication. Open its Build
link and wait for a successful Deploy stage (API: `latest_stage.name=deploy` and
`latest_stage.status=success`). The project's canonical production deployment must point to that
successful deployment. Then open `https://unifiles.dev/` and check content that changed in the new
version; an HTTP 200 or a familiar page title may still be the previous deployment.

GitHub Actions and Pages run independently on a push; the Actions build does not gate the Pages
build. Use a pull request for normal changes, review its checks and Pages preview, then merge to
`main` to publish. A successful GitHub Documentation workflow alone is only a build proof.

For local preflight, use an isolated environment with the same document dependencies:

```bash
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r requirements-docs.txt
.venv-docs/bin/python -m mkdocs build --strict
```

For an emergency manual deployment, build first and upload the resulting directory with:

```bash
python3 -m pip install -r requirements-docs.txt
python3 -m mkdocs build --strict
npx --yes wrangler pages deploy site --project-name unifiles-docs --branch main \
  --commit-hash "$(git rev-parse HEAD)" --commit-message "$(git log -1 --pretty=%s)"
```

Prefer the Git-connected automatic path. Do not put Cloudflare credentials in the repository; the
Wrangler command requires a separately authenticated local session or a protected CI secret.

## Package releases

Release tags are the only supported package publication entry point. The workflow validates that the tag
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
