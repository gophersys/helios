# Audit logging

Every state mutation writes an `AuditLog` row. This is non-optional and reviewed during incident response.

## The call

```python
from services.audit.logger import log_audit

log_audit(
    action="product.create",
    entity_type="Product",
    entity_id=product.id,
    details={"name": product.name, "variants": [v.id for v in product.variants]},
)
```

Place it **after** the DB mutation succeeds and **before** notifications or other side effects.

## Field conventions

- **`action`** — dotted lowercase, verb at the end: `<domain>.<entity>.<verb>` or just `<entity>.<verb>`. Examples: `product.create`, `product.delete`, `build.trigger`, `test.run.cancel`, `test.stage.complete`, `user.permission_set.assign`, `fixture.instance.bind_mtib`.
- **`entity_type`** — the Prisma model name in PascalCase: `Product`, `BuildRun`, `TestRun`, `User`, `Fixture`.
- **`entity_id`** — the UUID string. For composite entities, pick the most-specific id (e.g., `Execution.id`, not `TestRun.id`, when logging a stage transition).
- **`details`** — a JSON-serializable dict. Include the relevant before/after fields. Don't paste the whole entity.

## What to log

Every mutation. Examples:

| Handler | Action |
|---|---|
| `POST /v2/products` | `product.create` |
| `PUT /v2/products/<id>` | `product.update` |
| `DELETE /v2/users/<id>` | `user.delete` |
| `POST /v2/builds/trigger` | `build.trigger` |
| `POST /v2/runs/.../stage/<id>/complete` | `test.stage.complete` |
| `POST /v2/fixture-instances/<id>/bind-mtib` | `fixture.instance.bind_mtib` |

## What NOT to put in `details`

- JWTs, passwords, API keys, signed URLs.
- Raw request bodies (use selected fields).
- Personal data beyond what the entity itself holds.
- Anything you wouldn't want in a forensic export.

## Reads

Reads are not audited. The platform does not track who viewed what. If a read becomes sensitive enough that you want it logged, escalate to the architect agent — the answer is usually "redesign so the action that mattered is the mutation."

## Bulk operations

A single endpoint that mutates many rows writes one `AuditLog` per row. Use `details.batch_id` to group them if the caller wants to correlate. Don't replace many logs with one summary log — losing per-entity history defeats the point.

## Querying

The audit log is queryable via `/v2/audit?entity_type=...&entity_id=...&after=...`. Frontend admins surface this on the entity's detail page. When writing a new entity type, include the audit history view in the UI.

## Performance

`log_audit` is synchronous and writes to the same DB as the rest of the transaction. It's part of the user-visible latency. If a hot path is slow because of audit writes, that's a real problem — flag it, don't drop the audit.

## Init seed

Migrations don't write audit log entries. Seed scripts don't either. The audit log starts empty in a freshly seeded environment; only real user actions populate it.
