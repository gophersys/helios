# Orchestrator Knowledge — Living State

**Last updated**: 2026-03-27 (FUOTA validation passed on real hardware)

## Platform State

- **Branch**: `feature/validation-demo`
- **Staging**: DEPLOYED (revision 292) — all 7 pods running, 4 products seeded
- **Production**: Not yet deployed
- **FUOTA Validation**: 59 passed, 2 failed, 6 skipped (77 min, real hardware)
- **Backend tests**: 1194 passing
- **Frontend tests**: 398 passing
- **Build worker tests**: 30 passing

## End-to-End Proven (2026-03-27)

Full pipeline verified on real hardware:
1. Product.buildConfig (Alpha B0, from ck_boards) → Pipeline trigger (FUOTA, 7 builds)
2. Build worker claims jobs, clones repos, runs build.sh, produces build.json manifest
3. Artifacts uploaded to MinIO with role/processor/type metadata
4. Validation K8s Job triggered → ArtifactResolver downloads artifacts
5. J-Link flash (nRF52840 + modem + nRF9151) → POST (9/9) → Personalize → CoreCloud
6. FUOTA delivery (10 deliveries, all 100%) → Post-FUOTA verification
7. 3 of 5 FUOTA flows fully passed. 2 failed on COMMS MCUboot swap (firmware bug, not platform)

## Known Firmware Issue

**COMMS MCUboot swap failure on MFG→PROD transitions**: After FUOTA delivers PROD firmware (0.8.x) to a device running MFG (0.5.x), the APP processor swaps correctly but the COMMS processor stays on 0.5.x. MCUboot doesn't swap the secondary image. Likely version/signature mismatch between MFG and PROD comms MCUboot config. Affects test_02 and test_04. Firmware team needs to investigate.

## Session Summary (2026-03-26 to 2026-03-27)

### What Was Built
- Swarm skill with 9 agent prompts + self-updating knowledge
- Staging readiness audit (14+ issues fixed)
- API cohesion overhaul (permissions, audit logging, pagination, pipeline extraction)
- Secret management audit + cleanup (17 secrets mapped, naming standardized, gitignored overlay)
- Product & Build System architecture (ck_boards integration, discovery API, creation wizard)
- Artifact Contract (build.json manifest, ArtifactResolver, stage input contracts)
- 10 hardcoded alpha assumptions removed
- Build worker manifest generation
- ConfigMap auto-sync (ctl.sh)
- FUOTA test migration to ArtifactResolver
- Staging deployment + seed + real builds + real FUOTA validation

### Commits: ~35 total
### Architecture Docs: 3 (product-build-system, artifact-contract, build index)

## Remaining Work
- COMMS MCUboot swap investigation (firmware team)
- Vault deployment (architecture designed, not implemented)
- ck_boards git clone for board discovery API (returns 500 currently)
- Standard build runner (Python, replacing 47KB bash — architecture designed)
- Production deployment
- Frontend wiring to real discovery API (currently mock data)
