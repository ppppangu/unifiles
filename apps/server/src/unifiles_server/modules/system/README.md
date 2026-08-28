# System module

Owns public and authenticated service-health operations.

- implementation.py maps generated protocol DTOs to the system use cases.
- service.py owns health-result construction and is independent of FastAPI.
- dependencies.py defines object construction and request-time injection.

The generated router still reaches this provider through the temporary central
compatibility module. The router-factory phase moves the binding into api.py.
