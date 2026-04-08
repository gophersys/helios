# Zero-Downtime Updates

**Last reviewed:** 2026-04-07
**Status:** Active

> Every `helm upgrade` completes without dropping requests, losing builds,
> or leaving orphaned resources. Failed deploys auto-rollback.

---

## Overview

Concord runs 5+ services in Kubernetes. The build service processes firmware
builds that take 5–30 minutes. A naive `helm upgrade` would kill the build-service
pod mid-compile, orphan Docker containers, and lose build state. This document
describes how we prevent that.

```
                    SIGTERM received (helm upgrade)
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
          ┌──────────┐   ┌──────────┐   ┌──────────┐
          │ http-api  │   │build-svc │   │git-poller│
          │           │   │          │   │          │
          │ preStop:  │   │ preStop:  │   │ SIGTERM: │
          │ sleep 5s  │   │ /drain   │   │ finish   │
          │ (ingress  │   │ (mark    │   │ poll     │
          │  deregis- │   │  draining│   │ cycle    │
          │  ter)     │   │  → /ready│   └──────────┘
          │           │   │  returns │
          │ SIGTERM:  │   │  503)    │
          │ graceful  │   │          │
          │ shutdown  │   │ finish   │
          │ (close    │   │ current  │
          │  DB, etc) │   │ build    │
          │           │   │ (≤30m)   │
          │ 30s grace │   │          │
          └──────────┘   │ cleanup  │
                          │ Docker   │
                          │ container│
                          │          │
                          │ 40min    │
                          │ grace    │
                          └──────────┘
```

---

## 1. Build Service Graceful Drain

### Problem

Firmware builds take 5–30 minutes. A pod termination mid-build wastes
compute, leaves orphaned Docker containers, and the user sees a FAILED
build with no useful error.

### Solution

The build service implements a drain protocol:

1. **PreStop hook** — K8s sends `httpGet /drain` before SIGTERM
2. **Drain endpoint** — Sets `WorkerState.draining = True`
3. **Readiness gate** — `GET /ready` returns 503 when draining, removing
   the pod from service endpoints (no new job notifications arrive)
4. **Finish current build** — Worker loop completes the in-progress build
5. **Cleanup** — Docker builder container killed, workspace cleaned
6. **Exit** — Process exits, K8s replaces with new pod

```yaml
# build-service-deployment.yaml
terminationGracePeriodSeconds: 2400  # 40 min > max build (30 min)
lifecycle:
  preStop:
    httpGet:
      path: /drain
      port: 9002
```

### Orphan Container Cleanup

On **startup**, the build service runs `cleanup_orphaned_containers()`:
- `docker ps --filter name=concord-build-` to find lingering containers
- Kills each one (from a previous crash or unclean shutdown)

On **shutdown**, the current builder container (if any) is killed in the
`finally` block after the worker loop exits.

---

## 2. Heartbeat-Based Build Recovery

### Problem

When a build-service pod dies (OOM, node failure, etc.), builds stuck in
BUILDING state need to be detected and requeued. A simple `startedAt` timeout
fails because legitimate builds can take 30 minutes.

### Solution

Workers emit heartbeats every 60 seconds during active builds:

```
Worker                    HTTP-API                    Recovery Service
──────                    ────────                    ────────────────
  │ PATCH lastHeartbeat ──▶ │                              │
  │         (every 60s)     │                              │
  │                         │                              │
  │    [worker dies]        │                              │
  │                         │  ◀── check lastHeartbeat ────│ (every 2 min)
  │                         │                              │
  │                         │  lastHeartbeat > 5 min old   │
  │                         │  ──▶ reset to QUEUED ────────│
```

**Recovery logic** (`build_recovery.py`):

| Status | Detection | Timeout |
|--------|-----------|---------|
| CLONING | `startedAt` age | 5 minutes |
| BUILDING (with heartbeat) | `lastHeartbeat` age | 5 minutes |
| BUILDING (no heartbeat) | `startedAt` age | 30 minutes (legacy fallback) |

The 30-minute fallback handles builds that were started before the heartbeat
feature was deployed. Once all workers are updated, only the heartbeat path
fires.

**Permanent failure**: After 3 recovery attempts (`MAX_RECOVERY_ATTEMPTS`),
the build is marked FAILED to avoid infinite retry loops.

---

## 3. HTTP-API Connection Draining

### Problem

During a rolling update, the old pod may still be handling requests when the
ingress controller removes it from its backend list. Requests in flight get
dropped.

### Solution

A 5-second `preStop` sleep gives the ingress controller time to deregister
the pod before the application starts shutting down:

```yaml
# http-api-deployment.yaml
lifecycle:
  preStop:
    exec:
      command: ["sh", "-c", "sleep 5"]
```

Combined with `maxUnavailable: 0` in the rolling update strategy, this ensures:
1. New pod starts and passes readiness probe
2. Ingress routes traffic to both old and new pods
3. Old pod's preStop fires — 5s sleep
4. Ingress removes old pod from backends
5. Old pod receives SIGTERM, gracefully closes DB + MinIO + K8s clients

---

## 4. Atomic Helm Deploys

### Problem

A failed `helm upgrade` (bad image, migration error, probe failure) leaves
the cluster in a broken state requiring manual rollback.

### Solution

```bash
helm upgrade --install concord ... --wait --atomic --timeout 600s
```

- **`--atomic`** — Helm automatically rolls back to the previous release if
  any deployment fails to reach Ready within the timeout
- **`--timeout 600s`** — 10 minutes, accommodating build-service's longer
  startup (init container + image pull)
- **`--wait`** — Helm blocks until all resources are Ready

### Post-Deploy Smoke Tests

After Helm reports success, `_smoke_test()` hits each service's health endpoint:

| Service | Endpoint | Expected |
|---------|----------|----------|
| http-api | `/v2/docs` | 200 |
| frontend | `/` | 200 |
| build-service | `/health` | 200 |

If any smoke test fails, `_rollback_on_failure()` rolls back to the previous
Helm revision and exits with error.

### Rollback Flow

```
helm upgrade --atomic ──▶ Readiness fails? ──▶ Auto-rollback (--atomic)
                          │
                          ▼
                     Readiness OK ──▶ _smoke_test() ──▶ Fails? ──▶ _rollback_on_failure()
                                                        │
                                                        ▼
                                                   All pass ──▶ Deploy complete
```

---

## 5. PodDisruptionBudgets

PDBs protect services during **voluntary disruptions** (node drain, cluster
upgrade, spot eviction):

| Service | `minAvailable` | Rationale |
|---------|----------------|-----------|
| http-api | `replicas - 1` | At least one pod stays up during drain |
| build-service | 0 | Single replica; drain protocol handles it |
| frontend | 0 | Stateless, instant restart |
| git-poller | 0 | Stateless, picks up from last known state |

The build-service PDB works with the drain protocol: when draining, `/ready`
returns 503, the pod is not Ready, and the PDB allows the eviction. During
active builds, `/ready` returns 200, the pod is Ready, and an eviction
would respect the PDB (though `minAvailable: 0` allows it — the drain hook
fires first).

---

## 6. Rolling Update Strategy

All deployments use:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0    # Never remove pods before new ones are ready
    maxSurge: 1          # Add one pod at a time
```

This ensures zero-downtime: the old pod serves traffic until the new pod
passes its readiness probe.

---

## 7. Verification Checklist

After deploying zero-downtime changes:

```bash
# 1. Verify drain works
kubectl exec -n staging deploy/concord-build-service -- curl -s -X POST localhost:9002/drain
# Should return {"draining": true, ...}

# 2. Verify ready returns 503 after drain
kubectl exec -n staging deploy/concord-build-service -- curl -s -o /dev/null -w '%{http_code}' localhost:9002/ready
# Should return 503

# 3. Trigger a build, then immediately upgrade
nx update platform -c staging
# Build should complete on old pod, new pod takes over

# 4. Verify no orphaned containers
docker ps --filter name=concord-build-
# Should be empty after upgrade completes

# 5. Verify PDBs exist
kubectl get pdb -n staging
# Should show 4 PDBs
```

---

## Related

- [Build Service Architecture](../build/build-service.md) — pipeline stages, push delivery
- [Deployment Safety](../../../.claude/rules/deployment-safety.md) — rollback procedures
- [CI Pipeline](ci-pipeline.md) — overall CI/CD flow
