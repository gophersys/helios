# platform/services/databases

Shared database services — apps request a database via a contract CRD;
the platform provisions a logical database (or instance) and emits a
connection-string Secret.

## Components

- `postgresql/` — CloudNativePG operator (shared control plane, one logical
  DB per tenant app).
- `redis/` — Dragonfly or Redis operator (for cache / queue / session stores).

Add more only when a real consumer demands (e.g. Neo4j, ClickHouse).

## Fulfills
- `contracts/databases.md` — how apps declare a database requirement and
  receive a connection-string secret.

## Status

STUB.
