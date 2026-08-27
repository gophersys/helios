**Last reviewed:** 2026-03-31
**Status:** Draft

# US-002: Standardized Firmware Build Model

## Story

> As an engineer, I want a standardized way to represent firmware builds in Concord — whether built internally by the build service or uploaded externally from TeamCity — so that validation, manufacturing, and FUOTA can all consume build artifacts consistently.

## What a Build Looks Like

A firmware build for a multi-processor product (e.g., Alpha B0) produces artifacts for EACH target (AppID), following the [CK Firmware Versioning Spec](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046/Device+Firmware+Versioning+SS+V1.0).

### Example: Alpha B0 v0.5.2-BM (Bench Manufacturing)

```
Alpha B0 / v0.5.2 / Bench Manufacturing
├── Target 109 (app / nrf52840):
│   ├── 109.0.5.2-BM_app_nrf52840.hex          (plaintext, bootloader + app)
│   ├── 109.0.5.2-BM_app_nrf52840_encrypted.hex (encrypted, bootloader + encrypted app)
│   └── 109.0.5.2-BM.cfw                        (encrypted app only, for FUOTA)
│
├── Target 108 (comms / nrf9151):
│   ├── 108.0.5.2-BM_comms_nrf9151.hex          (plaintext)
│   ├── 108.0.5.2-BM_comms_nrf9151_encrypted.hex (encrypted)
│   └── 108.0.5.2-BM.cfw                        (encrypted, for FUOTA)
│
├── Modem: mfw_nrf91x1_2.0.2.zip                (Nordic modem firmware, if comms is nRF91xx)
└── manifest.json                                (build metadata)
```

### Naming Convention

**Version string**: `{AppId}.{Major}.{Minor}.{Build}-{Flags}`
- `109.0.5.2-BM` = AppID 109, version 0.5.2, Bench + Manufacturing

**Hex files**: `{VersionString}_{role}_{soc}[_encrypted].hex`
**CFW files**: `{VersionString}.cfw`
**Modem**: `mfw_{soc}_{modemVersion}.zip`

### Flags (per CK spec)
| Flag | Meaning |
|------|---------|
| B | Bench build (dev signing key) |
| E | Engineering build (eng signing key) |
| P | Production build (prod signing key) |
| M | Manufacturing firmware |
| D | Debug UART enabled |

### Release Tracks
Each build belongs to a release track determined by the signing key:
- **Bench**: Development/iteration. Signed with repo key.
- **Engineering**: Pre-production validation. Signed with eng key.
- **Production**: Shipped to customers. Signed with prod key.

Manufacturing firmware always matches the release track of its companion production firmware.

## Data Model

### FirmwareBuild (already exists, needs updating)

Represents a complete build for ONE target (one AppID). A full product build creates multiple FirmwareBuild records.

```prisma
model FirmwareBuild {
  id              String          @id @default(cuid())
  productId       String          // FK to Product
  targetId        String?         // FK to ProductTarget (appId + soc + role)

  // Version identity (per CK spec)
  version         String          // "0.5.2" (major.minor.build)
  versionString   String?         // "109.0.5.2-BM" (full string with AppId + flags)
  releaseTrack    String?         // "bench", "engineering", "production"
  isManufacturing Boolean @default(false)
  isDebug         Boolean @default(false)

  // Source
  source          String @default("upload") // "upload", "build-service", "teamcity"
  buildJobId      String?         // FK to BuildJob if built by Concord
  externalBuildId String?         // External build ID (TeamCity, etc.)

  // Artifacts (MinIO storage)
  hexStorageKey       String?     // Plaintext hex (bootloader + app)
  hexEncStorageKey    String?     // Encrypted hex
  cfwStorageKey       String?     // CFW binary (for FUOTA)
  modemStorageKey     String?     // Modem firmware zip
  manifestStorageKey  String?     // Build manifest JSON

  // Metadata
  filename        String
  sizeBytes       BigInt
  checksum        String          // SHA-256
  status          LifecycleStatus @default(ACTIVE)
  notes           String?

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  product Product        @relation(...)
  target  ProductTarget? @relation(...)
}
```

### FirmwareSet (new concept)

Groups FirmwareBuild records that were produced together (same build run, same version, same release track). A FirmwareSet for Alpha B0 would contain builds for both target 108 and 109.

```prisma
model FirmwareSet {
  id              String @id @default(cuid())
  productId       String
  boardRevisionId String?        // Which HW revision this targets

  version         String         // "0.5.2"
  releaseTrack    String         // "bench", "engineering", "production"
  isManufacturing Boolean @default(false)

  // Source
  source          String @default("upload")
  buildJobId      String?

  // Modem firmware (shared across targets)
  modemVersion    String?        // "2.0.2"
  modemStorageKey String?

  status          String @default("active") // active, deprecated, recalled
  notes           String?

  createdAt DateTime @default(now())

  product       Product        @relation(...)
  boardRevision BoardRevision? @relation(...)
  builds        FirmwareBuild[]
}
```

### How Firmware Gets Into Concord

**Path 1: Manual Upload** (Product > Firmware tab)
1. Engineer uploads hex/cfw files
2. Concord parses the version string from the filename
3. Creates FirmwareSet + FirmwareBuild records
4. Stores artifacts in MinIO

**Path 2: Build Service** (Concord internal)
1. Git push triggers build pipeline
2. Build service clones repo, runs west build
3. Produces artifacts per target
4. Creates FirmwareSet + FirmwareBuild records automatically
5. Artifacts stored in MinIO

**Path 3: External CI** (TeamCity webhook)
1. TeamCity build completes
2. Webhook notifies Concord with build artifacts
3. Concord downloads and stores them
4. Creates FirmwareSet + FirmwareBuild records

### How Validation Consumes Firmware

Validation stages reference a FirmwareSet:
- Stage needs "latest bench build of Alpha B0" → query FirmwareSet where product=Alpha, revision=B0, track=bench, latest
- Stage needs "specific version" → query by version string
- The FirmwareSet contains all targets → validation runner gets hex files for both app and comms processors
- Modem firmware included if applicable

### How Manufacturing Consumes Firmware

Manufacturing always uses manufacturing firmware (isManufacturing=true):
- Manufacturing station requests "manufacturing firmware for Alpha B0"
- Gets FirmwareSet where isManufacturing=true, revision=B0, latest active
- Flashes both processors + modem via J-Link

### Caching

FirmwareSet enables build caching:
- If the source commit hash + build config haven't changed, reuse the existing FirmwareSet
- The build fingerprint (hash of source + config) can be stored on FirmwareSet
- BuildJob already has `buildFingerprint` and `reusedFromId` for this purpose

## Next Steps

1. Update FirmwareBuild schema with new fields (versionString, releaseTrack, source, artifact keys)
2. Create FirmwareSet model
3. Build the Firmware tab UI (upload + browse)
4. Wire validation stage configs to reference FirmwareSet
5. Wire manufacturing to reference FirmwareSet
