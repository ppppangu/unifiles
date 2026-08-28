# @wyy/unifiles-generated

Generated TypeScript transport client and DTO package for the UniFiles API.

This artifact is the mechanical OpenAPI projection consumed at build time by
the handwritten `@wyy/unifiles` facade. It can be built and packed independently,
and it must never contain handwritten SDK behavior.

Do not edit files in this directory. Regenerate from the repository root:

    uv run python codegen/scripts/codegen.py generate sdk-typescript

Build the package with:

    npm run build --workspace @wyy/unifiles-generated
