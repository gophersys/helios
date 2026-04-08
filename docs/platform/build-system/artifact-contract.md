---
min_role: DEVELOPER
---
# Artifact Contract & Stage Interface Specification

**Last reviewed:** 2026-03-26
**Status:** Draft

> Self-describing build manifests that eliminate hardcoded App IDs, chip names,
> and filename pattern-matching across the entire pipeline. Every consumer reads
> the manifest instead of guessing.

!!! note "Upstream Spec"
    App IDs, version format (`major.minor.build`), release track flags, and CFW
    structure all follow the **Device Firmware Versioning SS V1.0** specification
    (Confluence). This document defines how Concord *implements* that spec in its
    build and validation pipeline.

---

## 1. The Problem

Today, builds produce files with ad-hoc naming and no manifest. Validation discovers artifacts by pattern-matching filenames — "starts with `109.`" means app processor, "starts with `108.`" means comms. App IDs, chip names, host types, device types, and J-Link families are hardcoded at six layers:

1. Build scripts
2. Pipeline artifact upload
3. PipelineAssets download/resolution
4. FUOTA client (CFW target construction)
5. FixtureController (flash target selection)
6. Test assertions (version string parsing)

Adding a second product requires changing code in 15+ files. A self-describing manifest fixes this by making every artifact queryable by role and type rather than by filename convention.

---

## 2. Build Manifest (build.json)

Every build MUST produce a `build.json` alongside its hex/cfw files. This is the single source of truth for what the build contains.

### Schema

```json
{
  "schemaVersion": 1,
  "product": "alpha",
  "board": "alpha_b0",
  "version": "0.8.3",
  "variant": "mfg",
  "track": "BM",
  "releaseTrack": "bench",
  "ncsVersion": "v2.9.0",
  "commitSha": "abc1234def5678",
  "branch": "main",
  "builtAt": "2026-03-26T18:30:00Z",

  "targets": [
    {
      "role": "app",
      "processor": "nrf52840",
      "appId": 109,
      "hostType": "HOST_TYPE_NRF52840",
      "jlinkFamily": "NRF52",
      "plaintextHex": "hex/109.0.8.3-BM.hex",
      "encryptedCfw": "cfw/109.0.8.3-BM.cfw"
    },
    {
      "role": "comms",
      "processor": "nrf9151",
      "appId": 108,
      "hostType": "HOST_TYPE_NRF9151",
      "jlinkFamily": "NRF91",
      "plaintextHex": "hex/108.0.8.3-BM.hex",
      "encryptedCfw": "cfw/108.0.8.3-BM.cfw"
    }
  ],

  "modemFirmware": {
    "chipset": "nrf9151",
    "file": "modem/mfw_nrf91x1_2.0.2.zip",
    "hostType": "HOST_TYPE_NRF9151"
  },

  "corecloud": {
    "deviceTypeId": 2,
    "deviceVariantId": 3,
    "apiEnv": "val"
  },

  "signing": {
    "keyFingerprints": {
      "109": "a1b2c3d4e5f6...",
      "108": "f6e5d4c3b2a1..."
    }
  }
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `schemaVersion` | Yes | Always `1`. Consumers check this before parsing. |
| `product` | Yes | Product name (matches `Product.name` in DB) |
| `board` | Yes | Board identifier from ck_boards |
| `version` | Yes | Semver build version |
| `variant` | Yes | Build variant: `mfg`, `debug`, `release` |
| `track` | Yes | CFW track string: `BM` (bench+mfg), `BMD` (bench+mfg+debug), `P` (production) |
| `releaseTrack` | Yes | Release track: `bench`, `engineering`, or `production`. Determines signing keys and bootloader ID. Sourced from `Product.buildConfig.releaseTrack`. |
| `ncsVersion` | Yes | nRF Connect SDK version used |
| `commitSha` | Yes | Full git commit hash |
| `branch` | Yes | Source branch |
| `builtAt` | Yes | ISO 8601 build timestamp |
| `targets` | Yes | Array of build targets (see below) |
| `modemFirmware` | No | Modem firmware blob, if the product includes a cellular SoC |
| `corecloud` | Yes | CoreCloud device identity for this product |
| `signing` | No | SHA-256 fingerprints per target, required for production builds |

### Target Fields

Each target produces **two** artifact types per the Device Firmware Versioning SS V1.0:

| Field | Description |
|-------|-------------|
| `role` | Logical role: `app`, `comms` |
| `processor` | SoC identifier: `nrf52840`, `nrf9151` |
| `appId` | CoreCloud application ID (integer) |
| `hostType` | MTIB gRPC `HostType` enum value for UART/flash routing |
| `jlinkFamily` | nrfjprog `-f` argument: `NRF52`, `NRF91` |
| `plaintextHex` | Merged bootloader + plaintext application Intel HEX. Used by validation for J-Link flashing. |
| `encryptedCfw` | Encrypted application image only, no bootloader. Used for FUOTA OTA delivery. `null` if CFW not produced for this target. |

**Why two artifact types?** J-Link flashing needs the full image (bootloader + app, plaintext) because it writes the entire flash. FUOTA delivery needs only the encrypted application because MCUboot on the device handles the swap. These are fundamentally different artifacts with different security properties — plaintext hex should never leave the build/test environment, while encrypted CFW is safe to transmit over the air.

### Design Decisions

**MFG App ID enforcement.** Manufacturing firmware MUST share the same App ID as production firmware for the same chipset. The system enforces this — MFG builds inherit App IDs from `Product.buildConfig.cfw.appIds`. There is no way to configure a different App ID for MFG vs production. This ensures FUOTA transitions between MFG and production firmware work without App ID mismatches.

**Release track determines signing.** The `releaseTrack` field (`bench`, `engineering`, `production`) controls which signing keys are used during the build and which bootloader ID is embedded in the CFW header. This is set in `Product.buildConfig.releaseTrack` and flows through to every build — it cannot be overridden per-build.

**FUOTA pre-flight validation.** Before a CFW is uploaded for FUOTA delivery, the system validates:

1. **Same App ID** — the CFW's App ID must match the device's current firmware App ID
2. **Same release track** — bench CFW can only update bench firmware, production can only update production (no cross-track FUOTA)
3. **Higher version** — `major.minor.build` must be strictly greater than the current version, except for MFG → production transitions where the version comparison is relaxed (MFG v0.5.0 → production v0.8.0 is valid regardless of track change)

These checks prevent accidental downgrades, cross-track contamination, and App ID mismatches that would cause the device to reject the update.

### Single-Processor Example (Sigma5)

```json
{
  "schemaVersion": 1,
  "product": "sigma5",
  "board": "sigma5_std",
  "version": "1.0.0",
  "variant": "release",
  "track": "P",
  "releaseTrack": "production",
  "ncsVersion": "v2.9.0",
  "commitSha": "789abcdef012",
  "branch": "release/v1.0",
  "builtAt": "2026-03-26T19:00:00Z",

  "targets": [
    {
      "role": "app",
      "processor": "nrf52840",
      "appId": 201,
      "hostType": "HOST_TYPE_NRF52840",
      "jlinkFamily": "NRF52",
      "plaintextHex": "hex/201.1.0.0-P.hex",
      "encryptedCfw": "cfw/201.1.0.0-P.cfw"
    }
  ],

  "corecloud": {
    "deviceTypeId": 5,
    "deviceVariantId": 1,
    "apiEnv": "val"
  }
}
```

One target, no modem firmware, no comms processor. The manifest describes exactly what is there — consumers iterate `targets[]` and handle whatever they find.

---

## 3. Artifact DB Model Enhancement

### Current State

The `BuildArtifact` model stores:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | String | Filename (e.g., `109.0.8.3-BM.hex`) |
| `storageKey` | String | MinIO object key |
| `sizeBytes` | Int | File size |
| `sha256` | String | Content hash |

To find "the app processor hex for this build," you parse the filename. This breaks when naming conventions change or a new product uses different patterns.

### Proposed Enhancement

Add structured metadata fields:

| New Field | Type | Values | Purpose |
|-----------|------|--------|---------|
| `role` | Enum | `app`, `comms`, `modem`, `log`, `manifest` | What this artifact represents |
| `processor` | String? | `nrf52840`, `nrf9151`, null | Which SoC (null for logs/manifests) |
| `artifactType` | Enum | `plaintext_hex`, `encrypted_cfw`, `log`, `manifest`, `metadata` | File format/purpose |

### Query Examples

With these fields, API queries become straightforward:

```
# Get all app processor hexes from pipeline 42
GET /v2/ci/builds/42/artifacts?role=app&artifactType=plaintext_hex

# Get all encrypted CFWs (for FUOTA upload)
GET /v2/ci/builds/42/artifacts?artifactType=encrypted_cfw

# Get the build manifest
GET /v2/ci/builds/42/artifacts?role=manifest
```

No filename parsing. No hardcoded App IDs. Works for any product.

---

## 4. Stage Input Contracts

Each validation stage requires specific artifacts. These contracts define the minimum artifact set — if any are missing, the stage should fail fast with a clear error rather than discovering the gap mid-test.

### Stage 1 — Smoke (Software Tests)

| Artifact | Role | Type | Purpose |
|----------|------|------|---------|
| build.json | manifest | manifest | Version and target metadata |
| App hex | app | hex | Flash and boot verification on native_sim |
| Comms hex | comms | hex | Flash and boot verification on native_sim |

No CFW needed — Stage 1 runs on `native_sim`, not real hardware. No FUOTA.

### Stage 2 — Driver (Driver Hardware Tests)

| Artifact | Role | Type | Purpose |
|----------|------|------|---------|
| build.json | manifest | manifest | Target metadata for flash routing |
| App hex | app | hex | Flash app processor via J-Link |
| Comms hex | comms | hex | Flash comms processor via J-Link |
| Mfg hex (app) | app | hex | Manufacturing firmware for shell-based driver tests |
| Mfg hex (comms) | comms | hex | Manufacturing firmware for shell-based driver tests |

Stage 2 needs manufacturing firmware because driver tests use the manufacturing shell to exercise individual peripherals.

### Stage 3 — Integration (Full Board Tests)

| Artifact | Role | Type | Purpose |
|----------|------|------|---------|
| build.json | manifest | manifest | Target metadata, version for assertions |
| Mfg hex (app) | app | hex | Manufacturing firmware (personalization, shell access) |
| Mfg hex (comms) | comms | hex | Manufacturing firmware |
| App debug hex | app | hex | Debug firmware (UART logging enabled) |
| App release hex | app | hex | Release firmware (production behavior) |

Integration tests flash multiple firmware variants to test transitions: mfg → debug → release.

### Stage 4 — Regression (Product Validation)

| Artifact | Role | Type | Purpose |
|----------|------|------|---------|
| Everything from Stage 3 | — | — | Full firmware set |
| CFW pair: version A (app) | app | cfw | FUOTA source firmware |
| CFW pair: version A (comms) | comms | cfw | FUOTA source firmware |
| CFW pair: version B (app) | app | cfw | FUOTA target firmware |
| CFW pair: version B (comms) | comms | cfw | FUOTA target firmware |

Stage 4 tests the full FUOTA cycle: upload CFWs, create plan, assign device, monitor progress, verify version after power cycle. Requires two distinct firmware versions (A → B).

### Stage 5 — Gate (PR FUOTA Validation)

| Artifact | Role | Type | Purpose |
|----------|------|------|---------|
| build.json | manifest | manifest | Version verification after FUOTA |
| Mfg hex (app) | app | hex | Flash base firmware for personalization |
| Mfg hex (comms) | comms | hex | Flash base firmware for personalization |
| Mfg CFW (app) | app | cfw | FUOTA base version |
| Mfg CFW (comms) | comms | cfw | FUOTA base version |
| PR CFW (app) | app | cfw | FUOTA target — the PR's firmware |
| PR CFW (comms) | comms | cfw | FUOTA target — the PR's firmware |

Gate tests flash mfg firmware via J-Link, personalize, then FUOTA to the PR's firmware. build.json provides expected version for post-FUOTA verification.

---

## 5. ArtifactResolver

A single Python class that replaces both `FW_*_HEX` environment variable paths and `PipelineAssets` filename parsing. Lives in `libs/python/corekinect/test/`.

### Interface

```python
from corekinect.test.artifact_resolver import ArtifactResolver

# Initialize with pipeline context
resolver = ArtifactResolver(
    pipeline_id="build-42",
    api_url="https://concord.local/v2",
    api_key="ck_run_..."
)

# Get a parsed build.json manifest
manifest = resolver.get_manifest("MFG_BASE")
# manifest.product == "alpha"
# manifest.targets[0].role == "app"
# manifest.targets[0].appId == 109

# Download a specific artifact by role + type
app_hex = resolver.get_artifact("MFG_BASE", role="app", type="hex")
# Returns: Path("/tmp/artifacts/109.0.8.3-BM.hex")

# Download all artifacts of a type
cfw_files = resolver.get_artifacts("MFG_BASE", type="cfw")
# Returns: [Path("108.0.8.3-BM.cfw"), Path("109.0.8.3-BM.cfw")]

# Get target metadata without downloading
app_target = resolver.get_target("MFG_BASE", role="app")
# app_target.appId == 109
# app_target.hostType == "HOST_TYPE_NRF52840"
# app_target.jlinkFamily == "NRF52"
```

### Design Principles

- **Product-agnostic** — uses `manifest.targets` to resolve artifacts, never hardcodes App IDs or processor names
- **Lazy download** — manifests are fetched on first access, artifacts downloaded only when requested
- **Local cache** — downloaded files are stored in a temp directory, re-used across multiple calls
- **Cleanup** — `resolver.cleanup()` removes all downloaded artifacts (called by test teardown)

### How It Replaces Current Code

| Current Approach | ArtifactResolver Equivalent |
|-----------------|---------------------------|
| `os.environ["FW_APP_HEX"]` | `resolver.get_artifact("MFG_BASE", role="app", type="hex")` |
| `PipelineAssets.download_artifact(name="109.0.8.3-BM.hex")` | `resolver.get_artifact("MFG_BASE", role="app", type="hex")` |
| `if filename.startswith("109"): target = "app"` | `manifest.targets` iteration — role is explicit |
| `APP_ID = 109` (hardcoded constant) | `resolver.get_target("MFG_BASE", role="app").appId` |
| `HOST_TYPE = HostType.HOST_TYPE_NRF52840` | `resolver.get_target("MFG_BASE", role="app").hostType` |

---

## 6. Product.buildConfig Flow

The complete chain from product definition to test execution, showing how metadata flows without hardcoding.

```
Product.buildConfig
    │
    │  targets: [{role: "app", processor: "nrf52840", appId: 109}, ...]
    │
    ▼
Pipeline Service
    │
    │  Creates build job with target metadata from buildConfig
    │
    ▼
Build Worker
    │
    │  Runs build hook → produces hex files
    │  Generates CFW files from hex outputs
    │  Writes build.json (populated from buildConfig)
    │  Uploads artifacts with role/processor metadata
    │
    ▼
Build API + MinIO
    │
    │  Stores artifacts with structured metadata
    │  build.json stored alongside hex/cfw files
    │
    ▼
Validation Runner
    │
    │  ArtifactResolver fetches build.json
    │  Reads targets[] — knows roles, processors, appIds, hostTypes
    │  Downloads artifacts by role + type
    │
    ▼
Test Code (product-agnostic)
    │
    │  for target in manifest.targets:
    │      flash(target.plaintextHex, family=target.jlinkFamily)
    │      open_uart(host_type=target.hostType)
    │      verify_version(target.appId, manifest.version)
```

### What Lives Where

| Metadata | Source of Truth | How It Gets to Tests |
|----------|----------------|---------------------|
| App IDs (108, 109) | `Product.buildConfig.targets[].appId` | build.json → `manifest.targets[].appId` |
| Processor names | `Product.buildConfig.targets[].soc` | build.json → `manifest.targets[].processor` |
| Host types | Derived from processor at build time | build.json → `manifest.targets[].hostType` |
| J-Link families | Derived from processor at build time | build.json → `manifest.targets[].jlinkFamily` |
| Device type/variant | `Product.buildConfig.cfw` | build.json → `manifest.corecloud` |
| File paths | Build worker output | build.json → `manifest.targets[].plaintextHex`, `.encryptedCfw` |

No test code needs to know that Alpha uses App ID 109 for its nRF52840. That information flows from the product definition through the build manifest to the test resolver.

---

## 7. Migration Path

### Phase 1: Add build.json Generation

**Where:** Build worker (end of build, before upload)

The build worker already has all the metadata — it just needs to serialize it. Generate `build.json` from the `buildConfig` + build outputs. Upload it alongside hex/cfw files.

### Phase 2: Enhance Artifact Model

**Where:** `prisma/schema.prisma`, build upload API

Add `role`, `processor`, `artifactType` fields to `BuildArtifact`. Populate during upload using metadata from `build.json`. Existing API responses gain new fields — backwards compatible.

### Phase 3: Implement ArtifactResolver

**Where:** `libs/python/corekinect/test/artifact_resolver.py`

Build the resolver class. Add it to `TestContext`. Initially, wire it up alongside existing `PipelineAssets` — both work in parallel during transition.

### Phase 4: Migrate Consumers

**Where:** All validation test code, FUOTA client, FixtureController

Replace one consumer at a time:

| Consumer | Current | After |
|----------|---------|-------|
| `PipelineAssets` | Filename pattern matching | `ArtifactResolver.get_artifact(role, type)` |
| FUOTA client | Hardcoded `APP_ID = 109` | `manifest.targets[].appId` |
| FixtureController | Hardcoded `HostType.HOST_TYPE_NRF52840` | `manifest.targets[].hostType` |
| Flash commands | Hardcoded `-f NRF52` | `manifest.targets[].jlinkFamily` |
| Version assertions | Regex on UART output with hardcoded patterns | `manifest.version` + `manifest.targets[].appId` |

### Phase 5: Remove Old Code

Once all consumers use `ArtifactResolver`:

- Delete `PipelineAssets` class
- Remove `FW_*_HEX` environment variables from K8s job specs
- Remove hardcoded App ID constants from test files
- Remove filename pattern-matching utilities

---

## Related Documents

- [Product & Build System](product-builds.md) — build config model and two-layer architecture
- [Build Service](build-service.md) — current build orchestrator (gRPC + HTTP)
- [Stages Overview](../../validation/stages-overview.md) — what each validation stage tests
- [Test Runner](../validation-system/test-runner.md) — test execution architecture
