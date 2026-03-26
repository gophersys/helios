# Orchestrator Knowledge — Living State

**Last updated**: 2026-03-26 (staging deployed, major overhaul session)

## Platform State

- **Branch**: `feature/validation-demo`
- **Staging**: DEPLOYED (revision 284) — all 7 pods running, seeded with 4 products
- **Production**: Not yet deployed
- **Backend tests**: 1194 passing
- **Frontend tests**: 398 passing
- **Build worker tests**: 28 passing
- **Validation tests**: 28 passing (ArtifactResolver)

## What Was Done This Session

### Phase 1: Staging Readiness Audit (9 agents, parallel)
- 14+ issues found and fixed: test failures, Helm values, stale paths
- All 9 domains audited and staging-ready

### Phase 2: API Cohesion Overhaul
- 4 security fixes (missing @require_permissions)
- 3 missing audit logging fixes
- 2 dead files deleted
- Pagination standardized (7 endpoints)
- Pipeline service extracted (1496→393 lines)
- Session types consolidated

### Phase 3: Secret Management
- Full secret audit across all 7 services (17 unique secrets mapped)
- 4 naming inconsistencies fixed
- 5 non-secrets moved from secrets: to config:
- Gitignored secrets overlay created
- Validation job creds parameterized
- .env.example files updated/created for all services
- Vault migration architecture designed (VSO approach)

### Phase 4: Product & Build System Architecture
- ck_boards integration designed (bare clone + worktree + board.yml/DTS parsing)
- Product Discovery API implemented (3 endpoints)
- Product creation wizard (frontend, 5-step flow)
- buildConfig JSON field on Product model
- Two-layer build system designed (standard runner + product hooks)
- 47KB build.sh analyzed line-by-line, feasibility confirmed
- REPO_PRODUCT_MAP and CI_TRIGGER_BRANCHES removed
- Per-product triggerBranches implemented

### Phase 5: Artifact Contract & Portability
- build.json manifest schema defined and implemented
- BuildArtifact model enhanced (role, processor, artifactType)
- ArtifactResolver implemented (replaces PipelineAssets)
- PipelineAssets deleted entirely
- 10 hardcoded alpha assumptions fixed
- Alpha seeded with full buildConfig + buildMatrix for all 5 stages
- All "v2" and "legacy" naming scrubbed

### Phase 6: Staging Deployment
- Old data archived (18MB pg_dump)
- Deployed to staging (282s total)
- Seed run: 4 products, 3 chipsets, 4 fixtures, 5 stage configs
- All endpoints verified with API key auth
- Board discovery needs ck_boards git clone (expected, not a blocker)

## Commits This Session: ~26 commits

## Known Remaining Work
- ck_boards git clone configuration for board discovery API
- Vault deployment (architecture designed, not implemented)
- Standard build runner implementation (architecture designed)
- Frontend needs real API wiring (currently mock data for discovery)
- Production deployment
- End-to-end build trigger test (webhook → pipeline → build → artifacts → validation)

## Architecture Docs Created
- `docs/architecture/build/product-build-system.md` — Product definition + build system
- `docs/architecture/build/artifact-contract.md` — Build manifest + stage contracts
- `docs/architecture/build/index.md` — Build section index

## Cross-Domain Integration Points (Updated)
- Product.buildConfig → Pipeline service → Build worker → build.json manifest → ArtifactResolver → Validation
- ck_boards (git) → Board Discovery API → Frontend wizard → Product creation
- Fixture profiles → Validation K8s jobs (MTIB info from fixture, not build)
- Per-product triggerBranches → Webhook handler → Pipeline creation
