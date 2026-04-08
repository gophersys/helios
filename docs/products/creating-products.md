---
min_role: DEVELOPER
---
# Creating Products

## UI

Open **Products**, click **Add Product**, and fill in three fields:

- **Name** — human-readable identifier ("Alpha B0")
- **Slug** — URL-safe string, auto-generated from the name (`alpha-b0`)
- **Description** — one sentence describing the device

## API

```bash
curl -X POST https://concord.local/v2/products \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alpha B0",
    "description": "Wearable health monitor, revision B0"
  }'
```

## Adding Board Revisions

Each revision maps to a distinct PCB version. When the board changes, create a new revision.

Open the product detail page, click **Add Revision**, set the revision name (B0, B1, C0), then define targets — one per processor:

| Field | Example | Notes |
|-------|---------|-------|
| Name | `app` | Short identifier for this target |
| Chipset | `nRF52840` | Drives toolchain selection in the build system |
| AppID | `109` | Must match the AppID in CFW filenames |

## Connecting Firmware Repos

The build system needs a source repo to compile from.

Open **Product > Settings > Firmware** and add a firmware source:

- **Repo URL** — Bitbucket or GitHub (`https://bitbucket.org/corekinect/alpha-fw`)
- **Build recipe** — which recipe compiles this firmware (see [Build Configuration](../builds/build-configuration.md))
- **Branch filter** — branches that trigger builds (default: `main`, `release/*`)

Build artifacts land in MinIO at `firmware-builds/{product}/{fw_type}/{variant}/{version}/`.
