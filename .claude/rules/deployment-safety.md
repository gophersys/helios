# Deployment Safety Rules

Prevent crashes, ensure smooth rollouts, maintain service availability.

## Helm Chart Safety Features

### Rolling Updates

All deployments use `RollingUpdate` strategy:

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0      # Never remove pods before new ones ready
      maxSurge: 1            # Add one pod at a time
```

This ensures:
- Old pods serve traffic until new pods are ready
- Readiness probes gate traffic to new pods
- Zero downtime during deploys

### Graceful Shutdown

Containers get `terminationGracePeriodSeconds` to finish requests:

```yaml
spec:
  terminationGracePeriodSeconds: 30
```

Backend must handle `SIGTERM`:
- Stop accepting new requests
- Finish in-flight requests
- Close database connections
- Exit cleanly

### Health Probes

Readiness probe gates traffic:
```yaml
readinessProbe:
  httpGet:
    path: /v2/docs
    port: 9001
  initialDelaySeconds: 10
  periodSeconds: 10
```

Liveness probe restarts unhealthy pods:
```yaml
livenessProbe:
  httpGet:
    path: /v2/docs
    port: 9001
  initialDelaySeconds: 30
  periodSeconds: 30
```

### Config Change Detection

Pod annotations trigger restarts on config changes:

```yaml
annotations:
  checksum/config: {{ sha256sum .configmap }}
  checksum/secret: {{ sha256sum .secrets }}
```

## Pre-Deploy Checklist

Before any deploy:

1. **Diff first**: `./deploy/ctl.sh staging diff`
2. **Check current state**: `nx run platform:status -c staging`
3. **Verify image exists**: `docker images | grep concord`

## Deploy Verification

After deploy:

```bash
# Check rollout status
kubectl rollout status deployment/concord-http-api -n staging

# Verify pods are ready
kubectl get pods -n staging -l app.kubernetes.io/name=concord-http-api

# Check logs for errors
kubectl logs -n staging -l app.kubernetes.io/name=concord-http-api --tail=50

# Test endpoint
curl -s https://staging.concord.local/v2/docs | head
```

## Rollback Procedures

### Quick Rollback (Helm)

```bash
# See history
helm history concord -n staging

# Rollback to previous
helm rollback concord -n staging

# Rollback to specific revision
helm rollback concord 5 -n staging
```

### Image Rollback

```bash
# Set specific image tag
helm upgrade concord ./deploy/production/helm/concord -n staging \
  -f ./deploy/production/helm/values-staging.yaml \
  --set httpApi.image.tag=staging-v1.2.3
```

### Restart Without Rollback

```bash
# If pods are stuck, restart deployment
kubectl rollout restart deployment/concord-http-api -n staging
```

## Breaking Changes

When deploying breaking changes:

1. **Database migrations**: Run in init container (automatic)
2. **API changes**: Version the endpoint (`/v2/` → `/v3/`)
3. **Config changes**: Ensure all envs updated before deploy

## Forbidden Actions

NEVER do these:

```bash
# NEVER force push to production without staging validation
./deploy/ctl.sh production deploy  # without staging first

# NEVER delete pods manually during deploy
kubectl delete pod concord-http-api-xxx

# NEVER scale to 0 during maintenance
kubectl scale deployment concord-http-api --replicas=0

# NEVER skip health checks
# (don't remove readiness/liveness probes)

# NEVER delete PVCs without a verified backup
kubectl delete pvc concord-postgres-pvc -n production  # DATA LOSS

# NEVER stop production without --confirm-delete
./deploy/ctl.sh production stop  # blocked by safety gate
```

## Incident Response

If deploy causes issues:

1. **Immediate**: `helm rollback concord -n staging`
2. **Verify**: `nx run platform:status -c staging`
3. **Investigate**: `kubectl logs -n staging -l app.kubernetes.io/name=concord-http-api --previous`
4. **Fix**: Address root cause before re-deploying
