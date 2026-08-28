# unifiles-generated

Generated Python transport client and DTO package for the UniFiles API.

This artifact is the mechanical OpenAPI projection consumed by the handwritten
`unifiles-client` facade. It can be built and tested independently, and it must
never contain handwritten SDK behavior.

Do not edit files in this directory. Regenerate from the repository root:

    uv run python codegen/scripts/codegen.py generate sdk-python

Build the package with:

    uv build --package unifiles-generated
