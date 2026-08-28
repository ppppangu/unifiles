# Files module

Owns file upload, listing, lookup, download, deletion, and supported-type
operations.

- implementation.py adapts HTTP and generated DTOs to file behavior.
- service.py contains transport-independent supported-type behavior.
- dependencies.py defines lightweight object construction.
- api.py statically composes generated routes with application providers.

Persistence and request identity still use the existing application context
during this staged move. They become explicit shared dependencies in the
remaining feature-module migration.
