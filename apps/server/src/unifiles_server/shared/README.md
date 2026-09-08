# Shared infrastructure

Contains cross-feature capabilities with stable semantics: request identity,
SQLite persistence, error envelopes, settings, and response mapping.

Feature-specific authorization and business rules must remain in their owning
module. Generated router factories receive shared authentication through each
feature's static router.py composition entry point.
