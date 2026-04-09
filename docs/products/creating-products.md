---
min_role: DEVELOPER
---
# Creating Products

Add a product through the UI wizard or the API.

## UI

Open **Products** → **New Product**. The wizard walks through branch selection, board family discovery, and SoC target configuration.

Three required fields:

- **Name** — human-readable identifier
- **Slug** — URL-safe string, auto-generated from name
- **Description** — one line

## API

```bash
curl -X POST /v2/products \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "...", "slug": "...", "description": "..."}'
```

## After creation

A new product has no board revisions, no repos, and no stage configs. Add them in order:

1. **Hardware tab** — add board revisions with SoC targets
2. **Repository settings** — link firmware repos
3. **Validation tab** — configure stages
