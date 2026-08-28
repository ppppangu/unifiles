# unifiles-server-protocol

Generated FastAPI protocol package for the UniFiles API.

This artifact contains transport DTOs, Base API interfaces, generated route
adapters, the canonical OpenAPI JSON document, and PEP 561 type information.
It is a library consumed by unifiles-server; it is not a runnable server.

Do not edit files in this directory. Regenerate from the repository root:

    npm run generate

Build the package with:

    uv build --package unifiles-server-protocol

Generated route factories receive implementation and security providers from
the consuming application. This package never imports unifiles_server.
