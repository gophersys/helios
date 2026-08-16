---
min_role: DEVELOPER
---
# Triggering Builds

## Build List

Open **Builds** to see all builds across products, newest first. Each entry shows:

- **Version** — firmware version (`0.5.2`)
- **Product** — which product this build targets
- **Firmware type** — MFG or production
- **Status** — queued, building, success, or failed
- **Trigger** — what started it (git push, manual, PR)
- **Commit** — source commit hash

Click any build to see its artifacts, compilation log, and metadata.

## Manual Trigger

### UI

Open **Builds**, click **Trigger Build**, select the product, firmware type, and branch, then click **Start**. Manual builds run through the same pipeline as automated ones — same caching, same artifact storage, same output paths.

### API

```bash
curl -X POST https://concord.local/v2/builds/trigger \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "productId": "<product-id>",
    "firmwareType": "alpha_mfg_fw",
    "branch": "main"
  }'
```

## Build Matrix

Each product defines which firmware types get built. Alpha B0 produces two:

| Firmware Type | Targets | Artifacts |
|---------------|---------|-----------|
| `alpha_mfg_fw` | nRF52840 (AppID 109), nRF9151 (AppID 108) | hex files + CFW files (bench+mfg track) |
| `alpha_fw` | nRF52840 (AppID 109), nRF9151 (AppID 108) | hex files + CFW files (production track) |

Both produce hex files for J-Link flashing and CFW files for FUOTA. The difference is in firmware features — MFG includes the manufacturing shell and debug logging, production strips both.

## Downloading Artifacts

### UI

Open a build, scroll to **Artifacts**, and click the download icon next to the file you need.

### API

```bash
# List artifacts
curl https://concord.local/v2/builds/<build-id>/artifacts \
  -H "Authorization: Bearer <token>"

# Download
curl -O https://concord.local/v2/builds/<build-id>/artifacts/<artifact-id>/download \
  -H "Authorization: Bearer <token>"
```

## Artifact Naming

Hex files follow `{version}_{target}_{chipset}.hex` — for example, `0.5.2_app_nrf52840.hex`.

CFW files follow `{appId}.{version}-{track}.cfw`. The track flags encode the build variant:

| Flag | Meaning |
|------|---------|
| B | Bench |
| E | Engineering |
| P | Production |
| M | Manufacturing |
| D | Debug |

So `109.0.8.3-BMD.cfw` is AppID 109 (nRF52840 app), version 0.8.3, built for bench + manufacturing + debug.
