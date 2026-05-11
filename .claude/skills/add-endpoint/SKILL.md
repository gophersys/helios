---
name: add-endpoint
description: Add a new v2 HTTP API endpoint following the standard handler shape (permissions → from_json → mutation → audit → notify → response).
argument-hint: "<METHOD> <path> — <one-line purpose>"
---

# /add-endpoint

Spawn `http-api-eng` (`.claude/agents/http-api-eng.md`).

## What the agent does

1. **Pick the domain folder**: `apps/backend/http-api/src/api/v2/<domain>/`. If the domain doesn't exist, create it (folder + `routes.py` + `<entity>.py` + `types.py`) and register it in `src/api/v2/router.py`.

2. **Add the permission constant**: in `src/lib/permissions.py` (or reuse an existing one).

3. **Write the handler** following the shape in `.claude/knowledge/conventions.md`:
   ```python
   @app.route("/v2/<domain>/...", methods=["..."])
   @require_permissions(Permissions.<DOMAIN>_<VIEW|MANAGE>)
   def <name>(...):
       payload = <Type>Request.from_json(request.json)
       # business logic
       row = await db.<model>.create(...)
       log_audit("<action>", "<Entity>", row.id, {...})
       notify_user(...)  # if user-relevant
       return jsonify(ApiResponse.ok(<Type>Response.to_json(row)))
   ```

4. **Define request/response types** in `<domain>/types.py` with `from_json` / `to_json` classmethods.

5. **Write tests** under `apps/backend/http-api/tests/<domain>/`. At minimum: golden path + one auth-failure case. Mark integration tests with `@pytest.mark.integration`.

6. **Update knowledge**: `.claude/knowledge/apps/backend/http-api.md`. Add the new module under "Internal structure". If you introduced a new pattern, note it under "Key patterns".

7. **Mirror frontend types**: hand off to `frontend-eng` to update `apps/frontend/app/src/lib/types/models.ts` (or ask the user to do it).

## Decision points the user must answer

- Does this need a Prisma model change? → also spawn `db-schema-eng`.
- Is this user-facing real-time? → wire a SocketIO emit + frontend subscription.
- Does it schedule a K8s Job? → use the `services/k8s/` client.

## Verify

```bash
nx test http-api -- tests/<domain>/
nx typecheck http-api
nx run http-api:lint
```
