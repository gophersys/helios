# Users & Roles

## Roles

Four roles, each a superset of the one below it:

| Role | What They Can Do |
|------|-----------------|
| **Admin** | Everything. Manage users, secrets, production deploys, system config. |
| **Maintainer** | Platform ops — products, MTIBs, fixtures, staging deploys. Can't manage users or touch production. |
| **Developer** | Builds, validation, test packages for products they have access to. |
| **Operator** | Manufacturing station only — scan devices, run POST, view results. |

Permissions follow the format `Concord.Admin.<Module>.<View|Manage>`. Admins have all permissions. Other roles get a subset based on the table above.

## Product Access

Beyond roles, each user gets per-product access levels:

| Level | Grants |
|-------|--------|
| `admin` | Full control over the product — edit settings, manage builds, assign users |
| `develop` | Trigger builds, run validation, upload test packages |
| `operate` | Run manufacturing POST, view results |
| `view` | Read-only access to builds, validation results, and product info |

A Developer with `develop` access on Alpha B0 can trigger builds and validation for that product, but can't see Sigma 5 unless separately granted access.

## Adding a User

### Via the UI

1. Go to **Settings > Users**
2. Click **Add User**
3. Enter their email (must match their Google OAuth account)
4. Select a role
5. Assign product access levels

### Via the API

```bash
# Create user
curl -X POST https://concord.local/v2/users \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "christian@corekinect.com",
    "name": "Christian Cortes",
    "role": "DEVELOPER"
  }'

# Grant product access
curl -X POST https://concord.local/v2/products/<product-id>/access \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "<user-id>",
    "level": "develop"
  }'
```

## API Keys for CI/Automation

API keys let CI pipelines and scripts authenticate without OAuth. They're scoped to a specific purpose and have a 24-hour expiry by default.

```bash
# Create an API key
curl -X POST https://concord.local/v2/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "staging-ci-pipeline",
    "expiresIn": "24h"
  }'
```

The response includes the key (prefixed `ck_run_`). Store it as a K8s secret or CI variable — it won't be shown again.

Validation runs create their own short-lived API keys automatically. You don't need to manage those.
