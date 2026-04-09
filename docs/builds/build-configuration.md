---
min_role: DEVELOPER
---
# Build Configuration

## Recipes

A build recipe tells the build service how to compile firmware for a specific product and variant. It specifies the toolchain, build commands, and which artifacts to extract. Recipes live in the firmware repo under `recipes/`:

```
recipes/
  alpha_mfg_fw/     # Manufacturing firmware — shell enabled, debug logging
  alpha_fw/          # Production firmware — no shell, quiet logging
```

Each recipe maps to a firmware type:

| Recipe | Firmware Type | Output |
|--------|--------------|--------|
| `alpha_mfg_fw` | Manufacturing | hex + CFW files, bench track, MFG shell active |
| `alpha_fw` | Production | hex + CFW files, production track, shell stripped |

Register recipes in Concord through the product's firmware settings. The build service reads the recipe on each job, so changes to the recipe in the repo take effect on the next build.

## Stage Configs

Stages control which firmware gets built and tested at each step of the validation flow. Configure them in **Products > Settings > Stages**:

| Stage | Firmware Built | Purpose |
|-------|---------------|---------|
| Smoke | MFG | Quick sanity check — does the board boot and respond? |
| POST | MFG | Full manufacturing production test on the fixture |
| Validation | MFG + Production | Complete test suite across both variants |
| FUOTA | Production CFW | Over-the-air update verification end-to-end |
| Release | Production | Final release candidate gate |

## CI Pipeline

The automated build runs on every qualifying commit:

1. **Git poller** detects new commits on watched branches
2. **Build service** picks up the job and compiles against the board target
3. **Artifacts** (hex, CFW) land in MinIO at `firmware-builds/{product}/{fw_type}/{variant}/{version}/`
4. **Concord API** records the build with metadata — commit hash, branch, version, artifact manifest

Builds are cached by content hash. If the source and toolchain haven't changed, the build is skipped and previous artifacts are reused. The cache key includes source file hashes, toolchain version, and recipe config.

### Branch Triggers

| Trigger | Behavior |
|---------|----------|
| Push to `main` | Automatic build of latest |
| Push to `release/*` | Automatic build of release candidate |
| Pull request opened/updated | Automatic build of PR artifacts (short-lived cache) |
| Manual (UI or API) | On-demand, same pipeline |
| Version file change | Automatic on detected version bump |

## Troubleshooting

**Build stuck in QUEUED** — the build service may be down or overloaded:
```bash
kubectl logs -n staging -l app.kubernetes.io/name=concord-build-service --tail=50
```

**Toolchain error** — the Docker build image is missing the right SDK version. Check the recipe's `Dockerfile` and verify the base image matches the expected Zephyr SDK.

**Artifacts not appearing** — check MinIO connectivity from the API pod:
```bash
kubectl exec -n staging deploy/concord-http-api -- \
  python3 -c "from minio import Minio; print(Minio('minio:9000').list_buckets())"
```

**Cache not working** — the build service logs the cache fingerprint on each job. Compare fingerprints between builds to find what changed:
```bash
kubectl logs -n staging -l app.kubernetes.io/name=concord-build-service | grep "fingerprint"
```
A different fingerprint means something in the source, toolchain version, or recipe config shifted.
