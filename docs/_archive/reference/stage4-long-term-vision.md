> **Archived 2026-03-30.** Planning note from 2026-03-06. The CI/CD pipeline vision described here is now implemented and documented in [architecture/platform/ci-pipeline.md](../../architecture/platform/ci-pipeline.md) and [architecture/build/build-service.md](../../architecture/build/build-service.md). Moved from `reference/` — planning notes are not lookup references.

# Stage 4 Long-Term Vision

## CI/CD Build + Validation Pipeline
User wants a backend build server that:
1. Has Bitbucket webhooks - push to branch triggers firmware build
2. PR creation triggers full Stage 4 validation suite
3. Flow: git push → build firmware → flash DUT → personalize → run tests → FUOTA lifecycle → report

## Architecture
- **Build service**: `docs/architecture/build-service.md` — library-first design
  - Core: `BuildEngine` class (transport-agnostic, all business logic)
  - gRPC wrapper: `providers/grpc_server.py` (port 50054)
  - HTTP wrapper: `providers/http_server.py` (Flask, port 8080)
  - Proto: `libs/protocols/build/build.proto`
  - Server: `apps/backend/build/`
- Build produces .hex (J-Link) + .cfw (FUOTA) artifacts, stored in MinIO
- Validation job triggered (K8s Job or similar)
- Job flashes DUT via MTIB, runs pytest suite, reports results
- FUOTA lifecycle: 5 phases, 6 FUOTA transitions (see `stage4-pr-validation-flow.md`)
- Results posted back to PR / dashboard

## Current State (2026-03-06)
- ctl.sh can build firmware locally via Docker
- MTIB gRPC can flash/personalize remotely
- pytest test suite written (99+ tests)
- Concord backend already has firmware build catalog API
- .cfw v2 generator: `libs/python/corekinect/firmware/cfw.py` (working)
- FUOTA API endpoints confirmed (see `fuota-api-workflow.md`)
- Missing: multipart upload support in CoreCloudRestInterface, FUOTA orchestration automation, webhook triggers

## FUOTA Validation Pipeline (planned)
1. Build firmware (3 variants: base, test, bump)
2. Generate CFW files (2 per build: AppId 108 + 109)
3. Upload CFW files to CoreCloud (`POST /singleton/firmwareimages`)
4. Create FUOTA plan with 3 stages (`POST /singleton/firmwareupdates/plans`)
5. Assign DUT to plan (`POST /singleton/firmwareupdates/settings/devices`)
6. Monitor progress (`GET /singleton/firmwareupdates/progress`)
7. Verify firmware version after each stage transition
8. Cleanup: disable FUOTA for DUT
