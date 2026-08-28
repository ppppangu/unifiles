# Shared infrastructure

Contains cross-feature capabilities with stable semantics: request identity,
SQLite persistence, error envelopes, settings, and response mapping.

Feature-specific authorization and business rules must remain in their owning
module. The top-level auth, errors, settings, store, and services modules are
temporary static compatibility exports and are removed after generated router
factories take over composition.
