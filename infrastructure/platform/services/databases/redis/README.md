# platform/services/databases/redis

Redis (or wire-compatible) for cache, queues, session stores, rate limiting.

## Default implementation

**Dragonfly** (Helm chart: `dragonflydb/dragonfly`) as the default because
of the better memory efficiency and multi-threaded architecture. Falls back
to `redis/redis` chart if an app specifically needs Redis internals (Lua
scripts, Redis modules).

One logical DB per tenant by default — namespaced via key prefix since
Redis-like stores don't have true multi-tenant isolation.

## Fulfills
- `contracts/databases.md` (Redis variant).

## Dependencies
- `platform/core/storage/` (for persistent cache, if enabled).

## Status

STUB. Deferred until a tenant app actually needs Redis — most current apps
use Postgres for everything.
