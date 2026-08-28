# System module

Owns public and authenticated service-health operations.

- implementation.py maps generated protocol DTOs to the system use cases.
- service.py owns health-result construction and is independent of FastAPI.
- dependencies.py defines object construction and request-time injection.

api.py statically binds the generated router factory to this module's
implementation provider and the shared authentication provider.
