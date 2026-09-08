# System module

Owns public and authenticated service-health operations.

- adapter.py maps generated protocol DTOs to the system use cases.
- service.py owns health-result construction and is independent of FastAPI.
- providers.py defines object construction and request-time injection.

router.py statically binds the generated router factory to this module's
adapter provider and the shared authentication provider.
