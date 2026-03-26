# Product & Build System Architecture

**Last reviewed:** 2026-03-26
**Status:** Draft

> Two-layer build system where products are derived from ck_boards (git source of truth),
> standard runner handles orchestration, and product-specific hooks handle the actual compilation.
> All configuration lives in Concord DB.

---

## 1. Overview

The current build system has several pain points: a monolithic 47KB `build.sh`, hardcoded product maps (`REPO_PRODUCT_MAP`), global trigger branch lists (`CI_TRIGGER_BRANCHES`), and no structured way to onboard new products. This redesign addresses all of them.

**Core principles:**

1. **ck_boards is the hardware source of truth** — board definitions, SoCs, revisions, and peripheral manifests all come from the `ck_boards` git repository. Concord reads this data and auto-populates Product records.
2. **Two-layer build** — A standard build runner (Python) handles everything generic (versioning, CFW generation, artifact validation, upload). A product-specific build hook (Bash) handles the actual `west build` invocations and product quirks.
3. **Config in DB, not in code** — Build configuration is a JSON blob on the Product model. Auto-populated from ck_boards discovery, confirmed by a human for AppIDs and device type.

---

## 2. ck_boards Integration

### Git Clone Strategy

The backend maintains a **bare git clone** of the ck_boards repository. For read operations, it creates lightweight **worktrees** checked out to the requested branch or tag. Worktrees are ephemeral — created on demand, used for parsing, then cleaned up.

```
/data/ck_boards.git/              # Bare clone (fetched periodically)
/data/ck_boards-worktrees/
    main/                         # Worktree for main branch
    release/v2.1/                 # Worktree for a release branch
```

### What Gets Parsed

**board.yml** — YAML file at the root of each board directory. Contains:

- Board name and description
- SoC list (e.g., `nrf52840`, `nrf9151`)
- Hardware revisions (e.g., `rev1.1`, `rev1.2`)
- Variants (e.g., `alpha_b0`, `alpha_b1`)

**DTS files** — Device Tree Source files for each revision. Parsed for `compatible` strings to extract the peripheral manifest:

- Sensors (accelerometer, PPG, temperature)
- Communication interfaces (UART, SPI, I2C)
- Power management ICs (BQ25180, BQ35100)
- GPIO expanders, EEPROMs, etc.

### Auto-Population Flow

```
ck_boards repo
    → git fetch + worktree checkout
    → parse board.yml (SoCs, revisions, variants)
    → parse DTS files (peripheral manifest via compatible strings)
    → auto-populate Product, Board, Revision, Chipset records
```

---

## 3. Product Discovery API

Three endpoints power the product creation wizard:

### List Branches

```
GET /v2/products/boards/branches
```

Returns all branches and tags from the ck_boards bare clone. Used as the first step in the wizard to select which branch to scan.

```json
{
  "data": {
    "branches": ["main", "release/v2.1", "feature/sigma5-rev2"],
    "tags": ["v1.0.0", "v2.0.0"]
  }
}
```

### Scan All Boards

```
GET /v2/products/boards/discover?branch=main
```

Checks out the requested branch, scans all board directories, returns a summary list. Lightweight — does not parse DTS files.

```json
{
  "data": [
    {
      "board": "alpha",
      "socs": ["nrf52840", "nrf9151"],
      "revisions": ["rev1.1", "rev1.2"],
      "variants": ["alpha_b0"]
    },
    {
      "board": "sigma5",
      "socs": ["nrf52840"],
      "revisions": ["rev1.0"],
      "variants": ["sigma5_std"]
    }
  ]
}
```

### Full Board Detail

```
GET /v2/products/boards/discover/{board}?branch=main
```

Deep scan of a single board — parses DTS files to extract the full peripheral manifest.

```json
{
  "data": {
    "board": "alpha",
    "socs": ["nrf52840", "nrf9151"],
    "revisions": [
      {
        "name": "rev1.2",
        "peripherals": [
          {"compatible": "bosch,bmi270", "type": "accelerometer", "bus": "spi"},
          {"compatible": "ti,bq25180", "type": "charger", "bus": "i2c"},
          {"compatible": "ti,bq35100", "type": "fuel-gauge", "bus": "i2c"},
          {"compatible": "nxp,tca9534a", "type": "gpio-expander", "bus": "i2c"},
          {"compatible": "pixart,pah8151", "type": "ppg", "bus": "spi"},
          {"compatible": "melexis,mlx90614", "type": "ir-temp", "bus": "i2c"}
        ]
      }
    ],
    "variants": ["alpha_b0"]
  }
}
```

---

## 4. Product Creation Wizard

The frontend walks through a linear wizard flow:

```
Select branch → Select board → Review auto-populated details → Confirm AppIDs + device type → Create
```

### Step 1: Select Branch

Calls `GET /v2/products/boards/branches`. User picks a branch (usually `main`).

### Step 2: Select Board

Calls `GET /v2/products/boards/discover?branch=main`. User picks a board from the list.

### Step 3: Review Auto-Populated Details

Calls `GET /v2/products/boards/discover/{board}?branch=main`. Displays:

- Hardware revisions with peripheral manifests
- Chipset list (SoCs)
- Suggested build configuration

### Step 4: Confirm Human-Required Fields

User provides or confirms:

- **AppIDs** — CoreCloud application identifiers per SoC target (e.g., 108 for nRF9151 comms, 109 for nRF52840 app)
- **Device type and variant** — CoreCloud device type/variant IDs
- **Firmware repositories** — Git URLs for app and comms firmware

### Step 5: Create

Single POST creates the full record tree:

- Product
- Board (linked to product)
- Revisions (linked to board)
- Chipsets (linked to revisions)
- 5 StageConfigs (one per validation stage, with defaults)
- buildConfig JSON (see next section)

---

## 5. Build Config Model

Build configuration is stored as a JSON blob in `Product.buildConfig`. It is auto-populated from ck_boards discovery, then refined by the human during the creation wizard.

### Alpha (Full Example — Dual-Processor)

```json
{
  "board": "alpha",
  "ncsVersion": "v2.9.0",
  "boardRoot": "ck_boards",
  "targets": {
    "app": {
      "soc": "nrf52840",
      "appId": 109,
      "role": "application"
    },
    "comms": {
      "soc": "nrf9151",
      "appId": 108,
      "role": "communications"
    }
  },
  "hasVsmMerge": true,
  "hasFips": false,
  "confFiles": {
    "app": ["prj.conf", "boards/alpha_b0_nrf52840.conf"],
    "comms": ["prj.conf", "boards/alpha_b0_nrf9151.conf"]
  },
  "overlays": {
    "app": ["boards/alpha_b0_nrf52840.overlay"],
    "comms": []
  },
  "postBuild": ["sign_mcuboot", "generate_dfu_package"],
  "cfw": {
    "deviceType": 2,
    "deviceVariant": 3
  }
}
```

### Sigma5 (Simplified — Single-Processor)

```json
{
  "board": "sigma5",
  "ncsVersion": "v2.9.0",
  "boardRoot": "ck_boards",
  "targets": {
    "app": {
      "soc": "nrf52840",
      "appId": 201,
      "role": "application"
    }
  },
  "hasVsmMerge": false,
  "hasFips": false,
  "confFiles": {
    "app": ["prj.conf"]
  },
  "overlays": {
    "app": []
  },
  "postBuild": ["sign_mcuboot"],
  "cfw": {
    "deviceType": 5,
    "deviceVariant": 1
  }
}
```

### Key Design Decisions

- **`targets` is a map, not an array** — keyed by role name (`app`, `comms`). Every target has an `appId` and `soc`. This naturally supports single-processor (one key) and dual-processor (two keys) products.
- **`overlays` is a per-target list** — additional DTS overlay files applied during `west build`. These are board-level overlays (e.g., enabling a peripheral), not test fixture adaptations.
- **`postBuild` is an ordered list** — steps run after `west build` completes. Product-agnostic steps like MCUboot signing are shared; product-specific steps like VSM merge are conditional on `hasVsmMerge`.
- **AppIDs come from humans** — ck_boards has no concept of CoreCloud AppIDs. These are assigned during product creation and stored here.
- **No MTIB/fixture config in builds** — MTIB hardware revision (1.1 vs 1.2) is a test fixture property, not a product property. Pin swap overlays, GPIO mappings, and other fixture-specific adaptations are handled at test time via fixture profiles, not at build time. The build system builds firmware for a *board*; the test fixture adapts for the *test hardware*.

---

## 6. Two-Layer Build System

### Layer 1: Standard Build Runner (Python, ~300 lines)

The runner is product-agnostic. It handles everything before and after compilation:

```
Version resolution (semver from git tags)
    → Invoke product build hook (Layer 2)
    → Collect outputs from OUTPUT_DIR
    → Generate CFW files (per target)
    → Validate artifacts (see Section 8)
    → Produce build.json v2
    → Stream logs to WebSocket
    → Upload to MinIO
```

**Responsibilities:**

- Parse `buildConfig` from Product record
- Resolve version from git tags + build number
- Set up `OUTPUT_DIR` and environment variables for the hook
- Call the product hook script
- Generate `.cfw` files from `.hex` outputs using the [CFW generator](../../reference/fuota-workflow.md)
- Validate all artifacts against the output contract
- Write `build.json` v2 (self-describing manifest)
- Stream build logs via WebSocket
- Upload final artifacts to MinIO

### Layer 2: Product Build Hook (Bash, ~200 lines)

The hook is product-specific. It lives in the Concord DB (stored as text on the Product model) and handles the actual compilation:

```bash
#!/bin/bash
# Product hook contract:
#   INPUT:  Environment variables (BOARD, NCS_VERSION, VERSION, OUTPUT_DIR, etc.)
#   OUTPUT: .hex files in OUTPUT_DIR/hex/
#   EXIT:   0 = success, non-zero = failure

# Example: Alpha dual-processor build
west build -b alpha_b0/nrf52840 app/ -- \
    -DBOARD_ROOT=$BOARD_ROOT \
    -DNCS_VERSION=$NCS_VERSION \
    -DOVERLAY_CONFIG="$APP_OVERLAYS"

cp build/zephyr/zephyr.hex "$OUTPUT_DIR/hex/109.${VERSION}.hex"

west build -b alpha_b0/nrf9151 comms/ -- \
    -DBOARD_ROOT=$BOARD_ROOT \
    -DNCS_VERSION=$NCS_VERSION \
    -DOVERLAY_CONFIG="$COMMS_OVERLAYS"

cp build/zephyr/zephyr.hex "$OUTPUT_DIR/hex/108.${VERSION}.hex"

# Product-specific: VSM library merge
if [ "$HAS_VSM_MERGE" = "true" ]; then
    python3 vsm_merge.py "$OUTPUT_DIR/hex/109.${VERSION}.hex"
fi
```

**Why Bash?** Build hooks deal with `west`, `cmake`, file copies, and shell tools. Bash is the natural language for this. Storing it in the DB means it can be versioned and updated without redeploying the build service.

### Interface Contract

The runner and hook communicate through a clean boundary:

| Direction | Mechanism | Contents |
|-----------|-----------|----------|
| Runner → Hook | Environment variables | `BOARD`, `NCS_VERSION`, `VERSION`, `OUTPUT_DIR`, `BOARD_ROOT`, `APP_OVERLAYS`, `COMMS_OVERLAYS`, `HAS_VSM_MERGE`, `HAS_FIPS` |
| Hook → Runner | Files in `OUTPUT_DIR/hex/` | `{appId}.{version}.hex` per target |
| Hook → Runner | Exit code | 0 = success, non-zero = failure |
| Hook → Runner | stdout/stderr | Captured and streamed as build log |

---

## 7. Build Output Contract

Every build MUST produce the following artifacts:

```
OUTPUT_DIR/
    build.json                    # v2 manifest (self-describing)
    build.log                     # Full build log
    hex/
        {appId}.{ver}-{track}.hex   # Plaintext hex per target (bootloader + app)
    cfw/
        {appId}.{ver}-{track}.cfw   # Encrypted CFW per target (app only, for FUOTA)
```

See [Artifact Contract](artifact-contract.md) for the full manifest schema and stage input contracts.

### build.json v2 Schema

```json
{
  "version": 2,
  "product": "alpha",
  "buildVersion": "0.8.3",
  "track": "BM",
  "buildNumber": 42,
  "timestamp": "2026-03-26T18:30:00Z",
  "commit": "abc1234",
  "ncsVersion": "v2.9.0",
  "targets": [
    {
      "appId": 108,
      "processor": "nrf9151",
      "role": "communications",
      "plaintextHex": "hex/108.0.8.3-BM.hex",
      "encryptedCfw": "cfw/108.0.8.3-BM.cfw"
    },
    {
      "appId": 109,
      "processor": "nrf52840",
      "role": "application",
      "plaintextHex": "hex/109.0.8.3-BM.hex",
      "encryptedCfw": "cfw/109.0.8.3-BM.cfw"
    }
  ]
}
```

The `targets` array is the key improvement over v1 — it makes the manifest self-describing. Consumers (FUOTA, validation, flashing) iterate over targets instead of hardcoding AppID assumptions.

---

## 8. Artifact Validation

The runner validates all artifacts before uploading to MinIO. Validation is mandatory and cannot be skipped.

### Mandatory Checks

| Check | What It Verifies |
|-------|-----------------|
| File existence | Every target in `build.json` has corresponding `.hex` and `.cfw` files |
| Hex format | Intel HEX files parse without errors |
| CFW header | Magic bytes, version field, appId match the expected values |
| Version consistency | Version in filenames matches `build.json` `buildVersion` |
| Target completeness | Number of hex/cfw pairs matches number of targets in `buildConfig` |

### CFW Header Integrity

CFW files include a header with metadata. The runner verifies:

- Magic bytes match CFW v2 format
- `appId` in header matches the target's configured appId
- `deviceType` and `deviceVariant` match the product's `cfw` config
- Version in header matches the build version

### Key Fingerprints

For production builds, the runner computes SHA-256 fingerprints of all artifacts and includes them in `build.json`:

```json
{
  "targets": [
    {
      "appId": 108,
      "hex": "hex/108.0.8.3-BM.hex",
      "hexSha256": "a1b2c3...",
      "cfw": "cfw/108.0.8.3-BM.cfw",
      "cfwSha256": "d4e5f6..."
    }
  ]
}
```

---

## 9. Branch Management

### Per-Product Trigger Branches

Each product has a `triggerBranches` array in its metadata:

```json
{
  "triggerBranches": ["main", "release/*"]
}
```

Webhook pushes to matching branches auto-trigger a build for that product. This replaces the global `CI_TRIGGER_BRANCHES` environment variable.

### Manual Triggers

Manual builds (via API or frontend) are unrestricted — any branch can be built manually regardless of `triggerBranches`. This supports development workflows where engineers build from feature branches.

### No Global Config

There is no global branch configuration. Each product controls its own trigger rules. This means:

- Adding a new product does not affect existing products
- Release branches can be product-specific
- Hot-fix branches only trigger the affected product

---

## 10. Migration from Current State

### What Gets Killed

| Current | Replacement |
|---------|-------------|
| `REPO_PRODUCT_MAP` env var | Product records in DB with `buildConfig` JSON |
| `CI_TRIGGER_BRANCHES` env var | Per-product `triggerBranches` array |
| `build.sh` (47KB monolith) | Standard runner (~300 lines) + product hook (~200 lines) |
| Hardcoded AppID mapping | `targets` map in `buildConfig` |
| Manual product onboarding | Product creation wizard with ck_boards auto-discovery |

### Migration Steps

1. **Deploy ck_boards integration** — bare clone + worktree support + discovery API
2. **Create product wizard** — frontend flow backed by discovery endpoints
3. **Migrate existing products** — run discovery against current ck_boards, populate `buildConfig` for Alpha and Sigma5, verify against current build outputs
4. **Deploy two-layer build** — standard runner + product hooks, run in parallel with old system
5. **Cut over** — switch webhook targets to new system, verify builds match
6. **Remove old system** — delete `build.sh`, remove `REPO_PRODUCT_MAP` and `CI_TRIGGER_BRANCHES`

### Backwards Compatibility

During migration, both systems run in parallel. The new system writes to the same MinIO paths, so downstream consumers (FUOTA, validation, flashing) work unchanged. The `build.json` v2 format is additive — v1 consumers can ignore the `targets` array.

---

## Related Documents

- [Build Service Architecture](build-service.md) — current build service design (gRPC + HTTP wrapper)
- [Builder Node Architecture](builder-nodes.md) — K8s DaemonSet for build workers
- [FUOTA Workflow](../../reference/fuota-workflow.md) — CFW file consumption by the FUOTA system
- [CI Pipeline](../platform/ci-pipeline.md) — current CI trigger and pipeline architecture
