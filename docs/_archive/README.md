# Archive

Historical documents preserved for context. These are **not active guidance** — they record completed work, superseded designs, and early-phase research.

## Contents

### plans/

Completed execution plans. The work described here has been implemented and is now documented in the active [validation/architecture/](../validation/architecture/) docs.

| Folder | What It Was | Outcome |
|--------|-------------|---------|
| `react-to-svelte/` | 4-tier plan for React → SvelteKit migration | **Completed** — frontend is pure SvelteKit |
| `system-monitor/` | 3-tier observability system plan | **Partially implemented** — observability exists, structured differently |
| `validation-stage3-and-4/` | Stage 3+4 proof-of-concept execution plan | **Completed** — see `validation/architecture/stage3-*`, `stage4-*` |
| `validation-stage4-proof/` | Stage 4 proof with CoreCloud integration | **Completed** — FUOTA verified working 2026-03-11 |
| `mtib-server-redesign.md` | MTIB server architecture redesign | **Completed** — implemented in `apps/edge/mtib-server-v2/` |
| `stage3-proof-execution-plan.md` | Stage 3 proof execution steps | **Completed** |
| `stage3-and-4-proof-execution-plan.md` | Combined Stage 3+4 execution steps | **Completed** |
| `validation-platform-cleanup.md` | Platform cleanup tasks | **Completed** |

### project/

Project management artifacts from the validation build-out.

| File | Description |
|------|-------------|
| `bom-validation-pipeline.md` | Bill of materials for validation infrastructure |
| `bom-system-implementation.md` | Implementation plan for BOM validation |
| `cohesion-review.md` | V1 cross-document consistency audit |
| `cohesion-review-v2.md` | V2 cross-document consistency audit |

### research/

Superseded research and analysis.

| Folder | Description |
|--------|-------------|
| `vsm/` | Vitals Sensor Module driver analysis (PAH8151 PPG, LSM6DSO motion, PSP library) — pre-Alpha product research |
| `power/` | IWSCK A0 power analysis and optimization logs |

### architecture/

Superseded architecture documents (v1, pre-final-architecture).

| File | Description |
|------|-------------|
| `manufacturing.md` | Early manufacturing system architecture (WIP) |
| `system.md` | Early system-level architecture (WIP) |
| `validation.md` | Early validation architecture — superseded by `validation/architecture/09-final-architecture.md` |

### post-mortems/

Incident analysis and lessons learned.

| File | Description |
|------|-------------|
| `mtib+logic.md` | MTIB + logic analyzer integration post-mortem |

### misc/

Other historical documents.

| File | Description |
|------|-------------|
| `client-analyzer-api.md` | Client analyzer API design (superseded) |
| `protocol-changes-analyzer.md` | Protocol change analysis tool design |
| `fuota-workflow-v1.md` | Earlier version of FUOTA workflow (superseded by `validation/reference/fuota-workflow.md`) |
