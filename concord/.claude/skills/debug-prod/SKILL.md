---
name: debug-prod
description: Investigate a production issue. Pulls logs, inspects state, isolates the failing component without making changes. Read-only until the user authorizes a fix.
argument-hint: "<symptom> — <when noticed>"
---

# /debug-prod

Spawn `architect` first (to scope the investigation), then the relevant specialist for hands-on debugging. Read-only mode until a fix is authorized.

## What the agent does

1. **Get a precise symptom**:
   - What does the user see? (404, 500, blank page, stuck loader, wrong data)
   - When did it start? (recent deploy? particular user action?)
   - Which env? (production almost always — staging issues use `/debug-prod` too)

2. **Pull the obvious sources** (read-only — don't `exec` anything that mutates):
   ```bash
   export KUBECONFIG=~/.kube/config-concord-remote
   kubectl -n production get pods                                     # status overview
   kubectl -n production logs deploy/concord-http-api --tail=200      # recent API logs
   kubectl -n production exec deploy/concord-http-api -- printenv | grep -E "APP_VERSION|GIT_COMMIT"
   ```

3. **Match symptoms to common failure shapes** (see `.claude/knowledge/workflows/debugging.md`):
   - `503 / connection refused` → pod restarting, OOMKilled (exit 137), or migration init failure
   - Stuck `Init` → `migrate-and-seed` failed (read its logs, look for `P3009`)
   - 401/403 on a route that worked yesterday → check JWT expiry, check permission set assignment, check `AUTH_ENABLED`
   - Wrong data → check the audit log via `/v2/audit?entity_type=...&entity_id=...`
   - Real-time updates missing → SocketIO connection lost? Check frontend devtools network tab

4. **Identify the affected service** and load its knowledge file. Don't speculate — confirm with the code.

5. **Reproduce locally** if at all possible. The compose stack is the safest place to iterate.

6. **Surface the root cause** with a clear write-up before proposing a fix.

7. **Propose a fix** only after the user reviews the root cause. The fix follows the normal flow (`/plan-feature` or a direct specialist hand-off depending on scope).

## Don't

- Don't `kubectl exec ... -- python -c "db..."` against production. State changes from a shell skip the audit log.
- Don't roll back production reflexively. Sometimes the issue isn't deploy-related, and a rollback wastes time. Identify the cause first.
- Don't restart pods to "see if it helps" without a hypothesis. That's not debugging.

## When to escalate

- If the issue affects data integrity → stop, write up the incident at `/home/bottinger/work/docs/incidents/`, and only proceed with explicit user direction.
- If the fix requires a schema migration → it's not a hotfix; plan the full prisma-flow.
