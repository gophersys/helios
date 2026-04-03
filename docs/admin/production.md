# Production Operations

## Deploy Flow

Always go through staging first. Never deploy directly to production.

```
development → staging → production
```

### 1. Deploy to Staging

```bash
./deploy/ctl.sh diff staging        # Preview changes
./deploy/ctl.sh staging deploy      # Build + push + helm upgrade
./deploy/ctl.sh staging status      # Verify pods are healthy
```

### 2. Validate on Staging

```bash
# Check API health
curl -s https://staging.concord.local/v2/docs | head

# Check logs for errors
kubectl logs -n staging -l app.kubernetes.io/name=concord-http-api --tail=50
```

### 3. Deploy to Production

```bash
./deploy/ctl.sh diff production     # Preview changes
./deploy/ctl.sh production deploy   # Build + push + helm upgrade
./deploy/ctl.sh production status   # Verify
```

## Rollback

If something breaks after a production deploy, roll back immediately. Investigate later.

### Helm Rollback (fastest)

```bash
# See release history
helm history concord -n production

# Roll back to previous release
helm rollback concord -n production

# Roll back to a specific revision
helm rollback concord 5 -n production
```

### Image Rollback

Pin a specific image tag if you need to go back further:

```bash
helm upgrade concord ./deploy/helm/concord -n production \
  -f ./deploy/helm/values-production.yaml \
  --set httpApi.image.tag=staging-v1.2.3
```

### Restart Without Rollback

If pods are stuck but the code is fine:

```bash
kubectl rollout restart deployment/concord-http-api -n production
```

## Database Migrations

Migrations run automatically via init container on deploy. Prisma runs `migrate deploy` before the API starts.

If a migration fails:
1. Check init container logs: `kubectl logs -n production <pod> -c init-migrate`
2. The API pod won't start until the migration succeeds
3. Fix the migration in code, redeploy to staging, verify, then push to production

Never run migrations manually in production. Always go through the deploy pipeline.

## Secret Rotation

### JWT Secret

1. Generate a new key: `openssl rand -hex 32`
2. Update `deploy/helm/values-production.yaml`
3. Redeploy — all existing tokens are invalidated, users will need to re-login

### CoreCloud API Keys

1. Get new keys from the CoreCloud admin panel
2. Update the `corecloud-validation` K8s secret in both `production` and `validation` namespaces
3. Restart the API pod: `kubectl rollout restart deployment/concord-http-api -n production`

### MinIO Credentials

1. Update Helm values
2. Redeploy — the MinIO pod will restart with new credentials
3. Verify artifact access still works

## Retention & Cleanup

**Build artifacts** — stored in MinIO under `firmware-builds/`. No automatic cleanup. Periodically review old builds and remove artifacts for deprecated products.

**Validation runs** — stored in PostgreSQL. Run data grows over time. Consider archiving runs older than 6 months.

**K8s Jobs** — validation runner jobs in the `validation` namespace. Completed jobs are cleaned up by K8s TTL controller (`ttlSecondsAfterFinished`). Failed jobs are kept for debugging — clean them manually:

```bash
kubectl delete jobs -n validation --field-selector status.successful=0
```

**Logs** — pod logs are ephemeral. If you need persistent logging, set up a log aggregator (Loki, ELK, etc.).
