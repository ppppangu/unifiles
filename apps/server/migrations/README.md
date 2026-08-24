# Database adapters

The runnable 0.1 single-node server uses SQLite and creates its schema automatically.

`postgres/` preserves the original `main` branch PostgreSQL schema work as reference for a future
shared production adapter. Those scripts are not executed by `unifiles-server` 0.1 and must not be
applied to the SQLite data directory.
