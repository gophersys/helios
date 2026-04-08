# Products

## What's a Product?

A product in Concord represents a hardware device that goes through firmware builds, validation, and manufacturing. Each product has:

- **Board revisions** — hardware variants (e.g., Alpha B0, Alpha B1). Different revisions can have different firmware, test fixtures, and validation stages.
- **Targets** — the processors on the board. Alpha B0 has two: nRF52840 (app, AppID 109) and nRF9151 (comms, AppID 108).
- **Firmware repos** — the source code that gets built into hex/CFW files.

## Creating a Product

### Via the UI

1. Go to **Products**
2. Click **Add Product**
3. Fill in:
   - **Name** — human-readable (e.g., "Alpha B0")
   - **Slug** — URL-safe identifier (e.g., `alpha-b0`), auto-generated from name
   - **Description** — what the device is, one sentence

### Via the API

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

Each revision represents a distinct hardware version. When the PCB changes, create a new revision.

1. Open the product detail page
2. Click **Add Revision**
3. Set the revision name (e.g., "B0", "B1")
4. Define targets — one entry per processor:

| Field | Example | Notes |
|-------|---------|-------|
| Name | `app` | Short identifier |
| Chipset | `nRF52840` | Used by build system |
| AppID | `109` | Matches CFW naming |

## Connecting Firmware Repos

Products link to firmware repositories for automated builds. The build system polls for changes and triggers builds when new commits land.

1. Go to **Product > Settings > Firmware**
2. Add a firmware source:
   - **Repo URL** — Bitbucket/GitHub repo (e.g., `https://bitbucket.org/corekinect/alpha-fw`)
   - **Build recipe** — which recipe to use (see [Build System](builds.md))
   - **Branch filter** — which branches trigger builds (default: `main`, `release/*`)

The product's firmware artifacts end up in MinIO under `firmware-builds/{product}/{fw_type}/{variant}/{version}/`.
