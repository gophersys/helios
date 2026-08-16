---
min_role: ADMIN
---
# Users & Roles

## Role Hierarchy

Four roles, each a superset of the one below it:

| Role | Scope |
|------|-------|
| **Admin** | Full system control — users, secrets, production deploys, system config |
| **Maintainer** | Platform ops — products, MTIBs, fixtures, staging deploys. No user management, no production access |
| **Developer** | Builds, validation, test packages for assigned products |
| **Operator** | Manufacturing station only — scan devices, run POST, view results |

Permissions follow the format `Concord.Admin.<Module>.<View|Manage>`. Admins hold all permissions; other roles get a subset matching their scope.

## Product Access

Beyond roles, each user has per-product access levels:

| Level | Grants |
|-------|--------|
| `admin` | Full product control — settings, builds, user assignment |
| `develop` | Trigger builds, run validation, upload test packages |
| `operate` | Run manufacturing POST, view results |
| `view` | Read-only — builds, validation results, product info |

A Developer with `develop` access on Alpha B0 can trigger builds and validation for that product but cannot see Sigma 5 unless separately granted access.

## Adding Users

### Via UI

Open **Settings > Users**, click **Add User**, enter their email (must match their Google OAuth account), select a role, and assign product access levels.

### Via API

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

## API Keys

API keys let CI builds and scripts authenticate without OAuth. They are scoped to a specific purpose and expire after 24 hours by default.

```bash
curl -X POST https://concord.local/v2/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "staging-ci-pipeline",
    "expiresIn": "24h"
  }'
```

The response includes the key (prefixed `ck_run_`). Store it as a K8s secret or CI variable — it won't be shown again.

Validation runs create their own short-lived API keys automatically. No manual management needed.
