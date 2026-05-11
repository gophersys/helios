# Concord — Glossary

Domain terms used across the codebase. These names are normative — don't invent synonyms.

Refresh this file when: a new domain concept is introduced, an existing one is renamed, or the lifecycle of a term changes.

## Hardware

- **DUT** — Device Under Test. The physical hardware being validated or manufactured (an Alpha, Sigma5, Theta board, etc.).
- **MTIB** — Manufacturing Test Interface Board. The fixture-side hardware that drives a DUT: power supplies, GPIO mux, UART, J-Link, ADC, current sense, optional motion control. Each MTIB is a K8s node running `mtib-server`.
- **Fixture** — A test rig: one or more MTIB slots wired to mate with DUTs. Has a `FixturePurpose`: `DEV` (accepts development packages) or `RELEASE` (released packages only).
- **Slot** — A position on a fixture that holds one DUT. A panel fixture has multiple slots; a standalone fixture has one.
- **Node** — A K8s node. `NodeType: MANUFACTURING | VALIDATION` for fixture nodes. Has `mtib_host` metadata pointing at the local `mtib-server` for that fixture.
- **Verdin** — Toradex Verdin iMX8MM ARM64 SoM. The compute behind every MTIB.
- **FluidNC** — Motion controller firmware on ESP32. Drives linear rails on motorized fixtures via grbl commands. Started/stopped by `mtib-server` via the `MOTION_*` RPCs; only enabled when fixture type is `VALIDATION`.

## Products

- **Product** — A canonical hardware product (Alpha B0, Sigma5, Theta, …). Gates builds, validation runs, manufacturing sessions, and asset uploads.
- **ProductVariant** — A board revision within a product (e.g., Sigma5 C0, C1). Builds target a variant.
- **AssetSet** / **TestPackage** — A bundle of binaries + test code uploaded for a variant. Status: `UPLOADING → DEVELOPMENT → RELEASED`. `RELEASED` packages run on `RELEASE` fixtures only.

## Builds

- **BuildRun** — A batch of `BuildJob`s triggered by one event (a commit, a webhook, a manual click). Tracks overall compile + validation status.
- **BuildJob** — A single firmware compilation. `BuildJobStatus: QUEUED, BLOCKED, CLONING, BUILDING, SUCCESS, FAILED, CANCELLED, CACHED`. Owned by `build-service`.
- **Codebase** — A logical source repo (e.g., `alpha_fw`, `sigma5_mfg_fw`). One Product can have multiple Codebases.
- **FirmwareVariant** — `smoke | debug | release | mfg`. Determines compiler flags and optimization.
- **ReleaseTrack** — `bench | engineering | production`. The promotion lane a build lives in.

## Validation & manufacturing

- **TestRun** — One end-to-end validation or manufacturing execution on a fixture. `TestRunStatus: PENDING, ACTIVE, COMPLETED, FAILED, CANCELLED`.
- **Stage** — A phase within a TestRun (electrical, fw_flash, smoke, etc.). One TestRun has many Stages.
- **Execution** — A single Stage's runtime row. Tracks `ExecutionStatus` and per-target results.
- **Target** — The specific DUT or slot a Stage runs against. A panel run has multiple targets per stage.
- **ManufacturingSession** — A batch of manufacturing TestRuns against a panel/lot. Bound to a Product + Fixture.
- **ValidationSession** — Same idea, validation side.

## Users & access

- **User** — A platform account. Authenticated via Google OAuth (production) or default-admin bypass (development).
- **Role** — `ADMIN | MAINTAINER | DEVELOPER | OPERATOR`. Global RBAC.
- **PermissionSet** — A named cluster of `Permissions.*` flags assigned to a User. Multiple Users can share a PermissionSet.
- **AccessLevel** — `view | operate | develop | admin`. Per-`Product` granular access on top of global Role.

## Observability & accountability

- **AuditLog** — A row written by `log_audit(...)` on every mutation. Action string, entity type+id, user, details JSON, timestamp.
- **Notification** — A row + SocketIO push. Persistent (in DB) + real-time (broadcast to `room=user:<id>`).
- **ErrorReport** — A surfaced production error tied to a Notification. Used by the `/error-reports` flow.

## Platform & infra

- **CI platform** — The separate Helm release in the `devops` namespace running nightly/weekly E2E pipelines. Independent of the main `concord` chart.
- **Office cluster** — The K3s cluster in the office. 3 control-plane + multiple agents + Verdin edges.
- **concord-remote** — Local tooling on the developer's WSL that tunnels K8s + registry traffic to the office cluster when off-site. See `/home/mateo/work/docs/CONCORD-REMOTE.md`.
- **CoreOps** — External device registry service. Binds `device_id ↔ SNR ↔ SIM/IMEI/EID`. Backend uses `corekinect.core_ops` to register devices post-manufacturing.
- **CoreCloud** — External device telemetry/OTA service.

## Versioning

- **VERSION file** — `/VERSION` at repo root. The single canonical concord platform version (e.g., `0.9.18`).
- **release tag** — `v<MAJOR>.<MINOR>.<PATCH>` annotated tag on `main`. Cut by the `/concord-release` skill.
- **image tag** — Built images are tagged `<MAJOR>.<MINOR>.<PATCH>` and additionally promoted via floating `:staging` / `:production` labels.

## Anti-glossary (don't use these)

- "pipeline run" → use **BuildRun**. (The schema was renamed; legacy references in archived docs only.)
- "device serial" → use **SNR**. SNR is the short stamped identifier; `device_id` is the CoreOps UUID. Don't conflate them.
- "test session" / "test job" → use **TestRun** (the platform concept) or **K8s Job** (the runtime object). Be specific.
