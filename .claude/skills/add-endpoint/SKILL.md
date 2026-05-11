---
name: add-endpoint
description: Add a new v2 HTTP API endpoint following the standard handler shape (permissions → from_json → mutation → audit → notify → response).
argument-hint: "<METHOD> <path> — <one-line purpose>"
---

# /add-endpoint

Spawn `http-api-eng` (`.claude/agents/http-api-eng.md`).

## Before you start: check dependencies

- **New Prisma model needed?** → first spawn `db-schema-eng` via `/add-prisma-model`. Endpoints that read or write a not-yet-existing model can't land until the migration is in. Run that flow to completion before continuing here.
- **Frontend consumer needed?** → after this endpoint lands, hand off to `frontend-eng` (or invoke `/add-page`). They'll mirror the response type in `apps/frontend/app/src/lib/types/models.ts` and add the UI.
- **New permission constant?** → covered in step 2. Real names follow `PRODUCTS_VIEW`, `BUILDS_TRIGGER`, etc. — no `ADMIN_` prefix.

## Authoritative knowledge to load

- `.claude/knowledge/apps/backend/http-api.md` — internal structure, where each domain lives, the services it depends on.
- `.claude/knowledge/conventions.md` — handler shape, response envelope, audit log conventions.
- `.claude/rules/auth-defaults.md` — `@require_permissions` is non-negotiable.
- `.claude/rules/audit-logging.md` — `log_audit(...)` on every mutation.

## What the agent does

1. **Pick the domain folder**: `apps/backend/http-api/src/api/v2/<domain>/`. If the domain doesn't exist, create it (folder + `routes.py` + `<entity>.py` + `types.py`) and register it in `src/api/v2/router.py` via the existing `register_<domain>_routes(api_blueprint)` pattern.

2. **Add the permission constant**: in `src/lib/permissions.py`, or reuse an existing one if the new endpoint shares scope. Use the verb that matches intent — `VIEW`, `MANAGE`, or a domain-specific verb (`TRIGGER`, `RUN`) where the granularity matters.

3. **Write the handler** following the shape in `.claude/knowledge/conventions.md`:
   ```python
   @app.route("/v2/<domain>/...", methods=["..."])
   @require_permissions(Permissions.<DOMAIN>_<VERB>)
   def <name>(...):
       payload = <Type>Request.from_json(request.json)
       # business logic
       row = await db.<model>.create(...)
       log_audit("<action>", "<Entity>", row.id, {...})
       notify_user(...)  # if user-relevant
       return jsonify(ApiResponse.ok(<Type>Response.to_json(row)))
   ```

4. **Define request/response types** in `<domain>/types.py` with `from_json` / `to_json` classmethods.

5. **Write tests** under `apps/backend/http-api/tests/<domain>/`. At minimum: golden path + one auth-failure case (401/403). Mark integration tests with `@pytest.mark.integration` — they require the compose stack.

6. **Update knowledge**: `.claude/knowledge/apps/backend/http-api.md`. Add the new module under "Internal structure". If you introduced a new pattern (e.g., a new auth bypass, a new background side effect), note it under "Key patterns".

7. **Mirror frontend types**: hand off to `frontend-eng` (or `/add-page`) to update `apps/frontend/app/src/lib/types/models.ts`. The contract is hand-synced — there is no codegen.

## Decision points

- **Is this user-facing real-time?** → wire a SocketIO emit + frontend subscription. See `.claude/knowledge/apps/backend/http-api.md` "Notifications" section.
- **Does it schedule a K8s Job?** → use the `services/k8s/` client. The runner-job pattern is documented in `.claude/knowledge/product-domains/validation.md` and `.claude/knowledge/product-domains/manufacturing.md`.
- **Does it call out to CoreOps or CoreCloud?** → use `corekinect.core_ops` / `corekinect.core_cloud` from the SDK; don't reimplement.

## Verify

```bash
nx test http-api -- tests/<domain>/
nx typecheck http-api
nx run http-api:lint
```

And manually hit the endpoint via Swagger at `http://localhost:9001/v2/docs` to confirm it's discoverable.
