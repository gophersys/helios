---
min_role: DEVELOPER
---
# Build Artifacts

Every successful build produces artifacts. At minimum, you get a hex file for J-Link flashing. Depending on the [build matrix](../products/build-matrix.md) configuration, you also get a CFW file for FUOTA and a `build.json` with metadata.

## Artifact types

| File | Format | Purpose |
|------|--------|---------|
| `*.hex` | Intel HEX | Flash via J-Link/SWD probe. Contains the raw firmware binary in hex-encoded format. Used by `nrfjprog --program` during manufacturing and validation. |
| `*.cfw` | Composite Firmware | Delivered over-the-air via FUOTA. Includes the application binary, version metadata, and signing information. The bootloader validates the CFW header before applying the update. |
| `build.json` | JSON | Build metadata: commit hash, branch, firmware version, board target, recipe name, and a manifest of all produced files with sizes and checksums. |

All three files have non-zero sizes. A zero-byte artifact indicates a build misconfiguration -- the recipe ran but failed to emit output via `concord_emit_hex` or `concord_emit_cfw`.

## Listing artifacts via API

```bash
curl https://concord.local/v2/builds/runs/<build-run-id>/artifacts \
  -H "Authorization: Bearer <token>"
```

Returns an array of artifact objects, each with `name`, `size`, and `contentType`. Filter by extension to find what you need:

```json
[
  { "name": "0.8.3_app_nrf52840.hex", "size": 524288, "contentType": "application/octet-stream" },
  { "name": "109.0.8.3-BMD.cfw", "size": 312400, "contentType": "application/octet-stream" },
  { "name": "build.json", "size": 1842, "contentType": "application/json" }
]
```

## Downloading artifacts

### Individual download

```bash
curl -O https://concord.local/v2/builds/runs/<build-run-id>/artifacts/<artifact-name>/download \
  -H "Authorization: Bearer <token>"
```

The response includes `Content-Disposition: attachment` with the original filename. The `<artifact-name>` is URL-encoded (spaces and special characters escaped).

### Bulk download

```bash
curl -O https://concord.local/v2/builds/runs/<build-run-id>/artifacts/download \
  -H "Authorization: Bearer <token>"
```

Returns a ZIP archive containing every artifact from the build. Content type is `application/zip` or `application/octet-stream`. Useful when you need the hex, CFW, and metadata together -- one request instead of three.

### UI download

Open the [build detail page](monitoring.md), wait for SUCCESS status, and click the **Download** button. The button triggers the bulk ZIP download. Individual file downloads are available in the artifact list if the build detail page renders one.

## Storage

Artifacts are stored in MinIO at:

```
firmware-builds/{product}/{fw_type}/{variant}/{version}/
```

The Concord API proxies downloads through presigned URLs. You never hit MinIO directly -- the API handles auth, logging, and URL generation.

Artifacts persist indefinitely. There is no automatic cleanup. Disk usage grows linearly with build count. Monitor MinIO capacity through the [platform status](../administration/production-operations.md) tooling.

## Using artifacts downstream

Hex files feed into two paths:

1. **Validation** -- the test runner flashes the hex onto the DUT via J-Link, runs the test suite, and reports pass/fail per stage. See [Validation](../validation/index.md).
2. **Manufacturing** -- the manufacturing station flashes the hex during POST (Production Operational Self-Test). See [Running POST](../manufacturing/running-post.md).

CFW files feed into FUOTA. The FUOTA stage uploads the CFW to CoreCloud, triggers an OTA campaign, and verifies the device applies the update and reboots with the new version.

The `build.json` metadata is consumed by the Concord API to record the build in the database and link artifacts to products, stages, and firmware versions.
