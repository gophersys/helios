# Builds

## Viewing Builds

Go to **Builds** in the sidebar. You'll see a list of all builds for your products, newest first. Each build shows:

- **Version** — firmware version (e.g., `0.5.2`)
- **Product** — which product it's for
- **Firmware type** — MFG or production
- **Status** — queued, building, success, or failed
- **Trigger** — what started the build (git push, manual, PR)
- **Commit** — the source commit hash

Click a build to see its artifacts, logs, and metadata.

## Triggering a Build

### From the UI

1. Go to **Builds**
2. Click **Trigger Build**
3. Select the product, firmware type, and branch
4. Click **Start**

### From the API

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

Builds triggered manually use the same pipeline as automated builds — same caching, same artifact storage.

## Build Matrix

Each product defines which firmware types get built. Alpha B0 builds:

| Firmware Type | Targets | Artifacts |
|---------------|---------|-----------|
| `alpha_mfg_fw` | nRF52840 (109), nRF9151 (108) | hex files, CFW files (bench+mfg track) |
| `alpha_fw` | nRF52840 (109), nRF9151 (108) | hex files, CFW files (production track) |

Both types produce hex files (for J-Link flashing) and CFW files (for FUOTA). The difference is in firmware features and the track flag in the CFW filename.

## Downloading Artifacts

### From the UI

1. Open a build
2. Scroll to **Artifacts**
3. Click the download icon next to the file you need

### From the API

```bash
# List artifacts for a build
curl https://concord.local/v2/builds/<build-id>/artifacts \
  -H "Authorization: Bearer <token>"

# Download a specific artifact
curl -O https://concord.local/v2/builds/<build-id>/artifacts/<artifact-id>/download \
  -H "Authorization: Bearer <token>"
```

### Artifact Naming

Hex files: `{version}_{target}_{chipset}.hex` (e.g., `0.5.2_app_nrf52840.hex`)

CFW files: `{appId}.{version}-{track}.cfw` (e.g., `108.0.5.2-BM.cfw`)

Track flags in CFW filenames:

| Flag | Meaning |
|------|---------|
| B | Bench |
| E | Engineering |
| P | Production |
| M | Manufacturing |
| D | Debug |

A CFW named `109.0.8.3-BMD.cfw` is AppID 109 (nRF52840 app), version 0.8.3, bench + manufacturing + debug track.
