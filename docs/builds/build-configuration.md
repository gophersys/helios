# Build System

## Build Recipes

A build recipe defines how to build firmware for a product. It specifies the toolchain, build commands, and output artifacts.

Recipes live in the product's firmware repo and are registered in Concord. Each recipe produces hex files (for J-Link flashing) and CFW files (for FUOTA).

Example recipe structure:

```
recipes/
  alpha_mfg_fw/     # Manufacturing firmware
  alpha_fw/          # Production firmware
```

Each recipe maps to a firmware type. Alpha has two:

| Recipe | Firmware Type | What It Builds |
|--------|--------------|----------------|
| `alpha_mfg_fw` | Manufacturing | MFG shell enabled, debug logging, bench track |
| `alpha_fw` | Production | No shell, quiet logging, production track |

## Stage Configs

Stages control which firmware gets built at each step of the validation pipeline. Configure stages per product in **Products > Settings > Stages**.

| Stage | Builds | Purpose |
|-------|--------|---------|
| Smoke | MFG firmware | Quick sanity check on fresh boards |
| POST | MFG firmware | Manufacturing production test |
| Validation | MFG + Production | Full test suite |
| FUOTA | Production CFW | Over-the-air update verification |
| Release | Production | Final release candidate |

## CI Pipeline

The build pipeline runs automatically:

1. **Git poller** watches configured branches for new commits
2. **Build service** picks up the change and starts a build job
3. **Artifacts** (hex, CFW) are stored in MinIO under `firmware-builds/{product}/{fw_type}/{variant}/{version}/`
4. **Concord API** records the build with metadata (commit hash, branch, version, artifact manifest)

Builds are cached by content hash. If the source hasn't changed, the build is skipped and the previous artifacts are reused. Cache keys include:

- Source file hashes
- Toolchain version
- Recipe config

### Build Triggers

| Trigger | When |
|---------|------|
| Git push to `main` | Automatic — builds latest |
| Git push to `release/*` | Automatic — builds release candidate |
| Pull request | Automatic — builds PR artifacts (not cached long-term) |
| Manual | Click **Trigger Build** in the UI or call the API |
| Version bump | Automatic — detected by version file change |

## Troubleshooting Failed Builds

### Build stuck in QUEUED

The build service might be down or overloaded. Check:

```bash
kubectl logs -n staging -l app.kubernetes.io/name=concord-build-service --tail=50
```

### Build fails with toolchain error

The Docker build image might be missing the right toolchain version. Check the recipe's `Dockerfile` and make sure the base image matches.

### Artifacts not appearing

Check MinIO connectivity:

```bash
kubectl exec -n staging deploy/concord-http-api -- \
  python3 -c "from minio import Minio; print(Minio('minio:9000').list_buckets())"
```

### Cache not working

If builds aren't being cached when they should be, check the cache fingerprint. The build service logs the fingerprint on each build:

```bash
kubectl logs -n staging -l app.kubernetes.io/name=concord-build-service | grep "fingerprint"
```

A changed fingerprint means something in the source or config changed. Compare fingerprints between builds to find what shifted.
