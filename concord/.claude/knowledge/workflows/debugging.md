# Debugging — knowledge

How to debug a Concord production or staging issue: where the logs live, how to read them with `kubectl`, how to query the audit log and notifications stream, and what the recurring failure shapes look like.

Refresh this file when: a new common failure shape is recognized, the K8s namespace layout changes, log retention policy changes, or new observability tooling is added.

## Prerequisites

- Kubeconfig for the office cluster — on-site `~/.kube/config`, off-site `~/.kube/config-concord-remote` (see `/home/bottinger/work/docs/CONCORD-REMOTE.md`).
- `kubectl` and the standard kube plugins (`stern` is handy but not required).
- For the audit log and notifications: an admin JWT or the dev bypass.
- Devcontainer running — never invoke `kubectl` from the host directly unless you're absolutely sure your kubeconfig is sane.

## Namespaces

| Namespace | Contents |
|---|---|
| `production` | The customer-facing platform. Treat as load-bearing. |
| `staging` | Pre-prod environment. Same chart, smaller-scale data. Safe to break. |
| `development` | K8s-managed dev jobs (validation runners, fixture deployments) when the dev developer points their local http-api at a real cluster. Distinct from local Docker Compose. |
| `devops` | The CI platform (separate Helm release; not the main `concord` chart). |

Always set the namespace explicitly. `kubectl` with no `-n` flag defaults to whatever's in the kubeconfig context — usually wrong.

## The flow

### 1. Confirm what's broken

The frontend symptom is rarely enough. Cross-reference:

- **HTTP API health**: `curl -fsS https://concord.corekinect.com/healthz` (production) or the staging equivalent.
- **Audit log**: did the action even get attempted? Query `/v2/audit?entity_type=<X>&entity_id=<Y>` or read `AuditLog` rows directly via DB.
- **Notification**: did the user receive a failure notification, or was it silent?
- **K8s pod state**: any pod not `Running`?

```bash
kubectl -n production get pods
kubectl -n production get pods --field-selector=status.phase!=Running
```

### 2. Read the logs

```bash
# Last 100 lines of http-api
kubectl -n production logs deploy/concord-http-api --tail=100

# Stream
kubectl -n production logs deploy/concord-http-api -f

# Previous container (after a crash)
kubectl -n production logs deploy/concord-http-api --previous

# A specific pod (when the deployment is multi-replica)
kubectl -n production get pods -l app=concord-http-api
kubectl -n production logs concord-http-api-7d9c8b5f4-x2k9p --tail=200

# Multiple deployments at once (requires stern)
stern -n production concord-
```

The init container output is separate. Migration failures live there:

```bash
kubectl -n production logs <pod> -c migrate-and-seed
```

### 3. Inspect environment + config

```bash
# What env vars the running container actually sees
kubectl -n production exec deploy/concord-http-api -- printenv | sort

# Mounted Secrets
kubectl -n production exec deploy/concord-http-api -- ls -la /etc/secrets

# Verify a specific Secret value (use sparingly, audited)
kubectl -n production get secret concord-http-api -o jsonpath='{.data.BITBUCKET_API_TOKEN}' | base64 -d
```

### 4. Shell into the pod

```bash
kubectl -n production exec -it deploy/concord-http-api -- bash
# Inside the pod
python3 -c "from database import db; ..."
```

This is the right place to run a one-off Prisma query against the real DB, dump a Notification batch, or trigger a manual `log_audit` rotation script.

### 5. Read the audit log directly

The audit log is the most-honest record of what happened. Two paths:

**Via API**:

```bash
TOKEN=$(kubectl -n production exec deploy/concord-http-api -- \
  python3 -c "from src.lib.tokens import mint_admin; print(mint_admin())")

curl -sS https://concord.corekinect.com/v2/audit \
  -H "Authorization: Bearer $TOKEN" \
  -G --data-urlencode "entity_type=TestRun" \
     --data-urlencode "entity_id=<id>" \
     --data-urlencode "after=2026-05-01T00:00:00Z" | jq .
```

**Via DB**:

```bash
kubectl -n production exec -it deploy/concord-http-api -- python3 -c "
from database import db
import asyncio, json
async def main():
    rows = await db.auditlog.find_many(
        where={'entityId': '<id>'},
        order={'createdAt': 'desc'},
        take=20,
    )
    for r in rows:
        print(r.createdAt, r.action, json.dumps(r.details))
asyncio.run(main())
"
```

### 6. Read the notifications stream

```bash
kubectl -n production exec -it deploy/concord-http-api -- python3 -c "
from database import db
import asyncio
async def main():
    rows = await db.notification.find_many(
        where={'userId': '<user_id>', 'createdAt': {'gt': '2026-05-01'}},
        order={'createdAt': 'desc'},
        take=20,
    )
    for r in rows: print(r.createdAt, r.type, r.title)
asyncio.run(main())
"
```

`/v2/notifications` covers the same thing over the API surface with pagination + filtering.

### 7. Error reports

Surfaced production errors flow through `ErrorReport` rows tied to a Notification of type `error_report`. UI at `/error-reports` in the SvelteKit app. Backend at `apps/backend/http-api/src/api/v2/system/error_reports.py`. Inspect with:

```bash
kubectl -n production exec -it deploy/concord-http-api -- python3 -c "
from database import db; import asyncio
async def main():
    rows = await db.errorreport.find_many(where={'status': 'OPEN'}, take=20)
    for r in rows: print(r.id, r.title, r.createdAt)
asyncio.run(main())
"
```

### 8. K8s job state for runners

Validation/manufacturing runners are K8s `Job` resources scheduled by the http-api. To find a runner:

```bash
# By TestRun
kubectl -n production get jobs -l concord.testrun=<run_id>

# By fixture
kubectl -n production get jobs -l concord.fixture=<fixture_id>

# Last 50 across all runners
kubectl -n production get jobs --sort-by=.metadata.creationTimestamp | tail -50

# Logs from the pod the Job spawned
kubectl -n production logs job/<job-name>
```

When a Job's pod fails, `kubectl describe pod <pod>` shows the termination reason — `OOMKilled`, `Error`, `Completed`, `DeadlineExceeded`.

### 9. MTIB / edge node debugging

MTIB servers run as K8s deployments on edge Verdin nodes:

```bash
# Which MTIB lives where
kubectl get nodes -l node.type=MANUFACTURING -o wide
kubectl get nodes -l node.type=VALIDATION -o wide

# MTIB pods on a specific node
kubectl get pods -A --field-selector=spec.nodeName=<verdin-hostname>

# Logs from a specific MTIB pod
kubectl -n production logs <mtib-pod> -c mtib-server -f

# Direct gRPC probe (from inside the cluster)
kubectl -n production exec deploy/concord-http-api -- grpcurl -plaintext <node-ip>:50053 list
```

`mtib-server` health is **never persisted** — http-api computes it live from K8s pod readiness + gRPC reachability. The DB stamp is `Node.disabled` (admin override only).

## Common failure shapes

### CrashLoopBackOff right after deploy

```
NAME                            READY   STATUS             RESTARTS
concord-http-api-7d9c-x2k9p     0/1     CrashLoopBackOff   5
```

Most common cause: migration failure. `kubectl logs <pod> -c migrate-and-seed` → look for `P3009 migration failed to apply cleanly`. Fix: hand-write a corrective forward migration (down-migrations aren't supported), redeploy.

Second most common: missing env var. Helm values updated for one env but not the other, or a Secret key renamed without rotation. `kubectl logs <pod>` → look for `KeyError`, `AttributeError: 'NoneType' object has no attribute 'split'` on startup.

See [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md) — every config change touches dev/staging/prod.

### OOMKilled — `exit code 137`

```
Last State:     Terminated
Reason:         OOMKilled
Exit Code:      137
```

The container ran past its memory limit. Find the limit:

```bash
kubectl -n production get deploy concord-http-api -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}'
```

Usual causes:

- Build worker downloaded a giant artifact into memory instead of streaming.
- HTTP API loaded an unbounded query result.
- A test runner kept the full pytest output in memory rather than spooling to MinIO.

Fix: stream, page, or spool. **Don't** just bump the limit — that's covering the bug. If the limit was genuinely tight, bump it in the helm values for all three envs.

### Notification was emitted but never received

Notifications dual-write: a `Notification` row goes to Postgres, and a SocketIO event fires to `room=user:<user_id>`. The DB row is the source of truth; the emit is best-effort.

To debug:

1. Confirm the row exists: query `notifications` table for the user/timestamp.
2. If the row exists but the user didn't see it — the SocketIO connection dropped. Frontend logs (`browser console`) will show reconnection attempts.
3. If the row doesn't exist — the handler bailed before calling `notify_user(...)`. Trace via audit log (the audit row precedes the notify by convention).

### Build worker silently stops picking up jobs

```bash
kubectl -n production logs deploy/concord-build-service --tail=100
```

Look for:

- `Permission denied (publickey)` — `BITBUCKET_SSH_KEY` rotated and the worker didn't restart. `kubectl rollout restart deploy/concord-build-service`.
- `MinIO 403` — `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_ACCESS_KEY` drift after a MinIO root password rotation.
- Worker idle but jobs exist — version mismatch. The worker filters by NCS version; an `ncs-v3.2.1` job won't be picked up by an `ncs-v2.7.0` worker.

### `Init:CrashLoopBackOff` on http-api

Init containers run in sequence (`migrate-and-seed` → `wait-for-deps` → main). If init crashes, the pod never starts. Logs:

```bash
kubectl -n <ns> logs <pod> -c migrate-and-seed
kubectl -n <ns> logs <pod> -c wait-for-deps
```

### Validation/manufacturing runner stuck `WAITING`

The runner deployment is up but heartbeats stopped flowing. `kubectl describe pod <runner-pod>`:

- `ImagePullBackOff` — registry CA cert expired or auth broke. The mtib devcontainer rebuild + push is the usual fix; check `.devcontainer/ctl.sh:install_registry_certs`.
- Pod is `Running` but no heartbeat — the runner can't reach http-api. Check `CONCORD_API_URL` env, NetworkPolicy, DNS.
- Pod evicted — node went `NotReady`. `kubectl get nodes` → describe the affected node.

### MTIB returns gRPC `UNAVAILABLE`

```
RuntimeError: failed to connect to <verdin-host>:50053
```

Order to check:

1. Pod readiness: `kubectl get pod -l concord.fixture=<id>`. If `0/1`, look at the pod logs and events.
2. Node disabled? `kubectl get node <verdin-host> -o yaml | grep disabled` — manually-set `disabled=true` removes from rotation.
3. The Verdin SoM rebooted (power blip, watchdog). Wait 60s for K8s to reschedule.
4. The MTIB hardware itself failed — power supply, USB hub, MTIB rev mismatch.

## Quick reference

```bash
# Current pod state across the namespace
kubectl -n production get pods,jobs,deployments

# Resource usage
kubectl -n production top pods

# Events for a specific entity
kubectl -n production describe pod <pod>
kubectl -n production get events --sort-by='.lastTimestamp' | tail -50

# Restart a deployment
kubectl -n production rollout restart deploy/concord-http-api
kubectl -n production rollout status deploy/concord-http-api

# Roll back
nx rollback platform -c production    # preferred
kubectl -n production rollout undo deploy/concord-http-api  # last resort

# Diff what's deployed against the chart on disk
nx diff platform -c production
```

## Related knowledge

- [`local-dev.md`](local-dev.md) — reproducing prod failures locally
- [`testing.md`](testing.md) — regression-test what you fix
- [`credentials.md`](credentials.md) — `kubectl get secret` flow
- [`../architecture.md`](../architecture.md) — what each pod actually does
- [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md) — why so many bugs come from one-env config drift
- [`../../rules/audit-logging.md`](../../rules/audit-logging.md) — what the audit log will and won't tell you
- `/home/bottinger/work/docs/CONCORD-REMOTE.md` — off-site cluster access
- `/home/bottinger/work/docs/incidents/` — postmortems for prior failures
