# Initial Setup

## Cluster Requirements

Concord runs on K3s with Traefik as the ingress controller. You'll need three namespaces:

- `staging` — pre-production validation
- `production` — live system
- `validation` — test runner jobs (K8s Jobs spawned per validation run)

Minimum hardware: 4 CPU, 8GB RAM, 100GB storage. MinIO needs its own PV for firmware artifacts.

## First Deploy

Start with staging. Production comes after you've verified everything works.

```bash
# Full first-time setup (bootstraps infrastructure + deploys apps)
nx start platform -c staging

# Verify pods are healthy
nx run platform:status -c staging
```

The deploy bootstraps the cluster (namespaces, RBAC, certs, secrets), creates the PostgreSQL database, runs Prisma migrations + seed via init container, and starts all services.

## Creating the First Admin User

After the first deploy, you need to seed an admin user. Hit the API directly:

```bash
curl -X POST https://staging.concord.local/v2/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mateo@corekinect.com",
    "name": "Mateo Segura",
    "role": "ADMIN"
  }'
```

This only works when `AUTH_ENABLED=false` (the default for first setup). Enable auth after creating the admin account.

## Configuring Auth

Concord uses Google OAuth with JWT tokens. Auth is toggled via the `AUTH_ENABLED` environment variable.

1. Set your Google OAuth client ID and secret in the Helm values:

```yaml
# deploy/production/helm/values-staging.yaml
httpApi:
  env:
    AUTH_ENABLED: "true"
    GOOGLE_CLIENT_ID: "<your-client-id>"
    GOOGLE_CLIENT_SECRET: "<your-client-secret>"
    JWT_SECRET: "<random-256-bit-key>"
```

2. Redeploy:

```bash
nx update platform -c staging
```

3. Verify auth is working — unauthenticated requests should return 401:

```bash
curl -s https://staging.concord.local/v2/products
# Should return {"errors": ["Unauthorized"]}
```

## Setting Up Secrets

Three categories of secrets need configuration:

**JWT signing key** — used for auth tokens. Generate a random key:

```bash
openssl rand -hex 32
```

**CoreCloud API keys** — needed for device registration, FUOTA, and telemetry. Get these from the CoreCloud admin panel. The validation API key goes in the `corecloud-validation` K8s secret in both `staging` and `validation` namespaces.

**MinIO credentials** — S3-compatible storage for firmware artifacts. Set in Helm values:

```yaml
minio:
  rootUser: "concord-admin"
  rootPassword: "<strong-password>"
```

Every config field must exist in all three environment files:

| File | Environment |
|------|-------------|
| `deploy/development/.env` | Development |
| `deploy/production/helm/values-staging.yaml` | Staging |
| `deploy/production/helm/values-production.yaml` | Production |

Add a new secret to one, add it to all three.
