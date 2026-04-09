---
min_role: ADMIN
---
# API Keys

API keys give scripts, CI builds, and CLI tools authenticated access to Concord without going through OAuth. Each key is tied to the user who created it and inherits that user's permission set.

## Creating a Key

Open the sidebar and click **Settings**. In the settings dialog, switch to the **API Keys** tab. The tab describes its purpose: programmatic access to the Concord API.

Click **Create API Key** and enter a name -- something that identifies the use case, like "staging-ci-pipeline" or "manufacturing-reporter". Click **Create**.

Concord returns the full key exactly once. It looks like `ck_live_...` followed by a long random string. Copy it now and store it in your CI secrets, a K8s secret, or a password manager. After you close this dialog, the full key is gone -- Concord only stores a hashed version.

## Key Visibility

The API Keys list shows each key's name, creation date, and a prefix (the first several characters of the key). The full key never appears in the list. This is intentional -- if someone gains read access to the settings page, they cannot extract usable credentials.

## Using a Key

Pass the key in the `Authorization` header with the `ApiKey` scheme:

```bash
curl -H "Authorization: ApiKey ck_live_abc123..." \
  https://concord.local/v2/products
```

The key authenticates as the user who created it. If that user has `products:view`, the call succeeds. If the user lacks `builds:manage`, a build trigger call returns `403`.

## Revoking a Key

Click **Revoke** (or **Delete**) next to any key in the list. The key stops working immediately -- any request using it gets a `401 Unauthorized` response. There is no grace period and no undo.

Revoke keys when:

- The secret was exposed (leaked in logs, committed to a repo)
- The CI build or script no longer needs access
- An employee with API keys leaves the team

## Multiple Keys

A user can hold multiple active API keys simultaneously. Each key operates independently -- revoking one doesn't affect the others. This lets you scope keys to different systems (one for CI, one for the manufacturing reporter, one for a monitoring script) and rotate them individually.

## Who Can Manage Keys

Admins can create and revoke keys for any user. Developers also have the `api-keys:manage` permission, so they can create keys for their own account without asking an Admin.

Operators and Maintainers without explicit `api-keys:manage` permission cannot create keys.

## Related

- [Permission Sets](permission-sets.md) -- the permissions a key inherits from its user
- [REST API](../reference/rest-api.md) -- endpoint reference for authenticated API calls
- [corectl CLI](../reference/corectl.md) -- CLI tool that uses API keys for authentication
