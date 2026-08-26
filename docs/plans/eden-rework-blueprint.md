# eden rework — architecture blueprint

```
┌─ LEDGER #130 · eden rework · FINAL · 2026-08-25 ─────────────────────────────┐
│ PLAN     19.25 agent-days · P0 2.5 · P1 8.25 · P2 6.75 · P3 1.75             │
│ P0 gates real · P1 env machinery + skeleton · P2 create a project (eden IS   │
│ the template) · P3 the board, co-designed                                    │
│ SHAPE    1 product · 1 image in P0–P3 · 1 chart · 2 RPCs · 2 env profiles    │
│          (prod is Argo's) · 8 L1 capability members, 7 required, 10 probes   │
│ NEEDS YOU  4 decisions (§8): D1 domain+auth · D2 staging cluster ·           │
│            D3 the library contract · D4 the survive/rewrite ledger           │
│ SHIP GATE  all five round-7 pillars, not just #92 (§0.2). Pillar 4 has no    │
│            phase item; pillars 3/4/5 sit outside these agent-days.           │
│ DEFERRED 31 ledger rows, every one with a stated trigger.                    │
│ HISTORY  10 adversarial passes: 26 → 14.25 → 18.5 → 17.5 → 17.75 → 19 → 20   │
│          → 21.25 → 21 → 19.5 → 19.25. Revision log at the end.               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Ledger #130.** Drafted 2026-08-25 from the 7-round design interview
(`eden-rework-intent.md`) and the approved CI contract (`cictl-org-contract-proposal.md`).
The intent is the authority. Nothing here contradicts it.

**Evidence base — working trees read on 2026-08-25.** `eden` `7b41f06`;
`libs` submodule `a0402e1`; `.devcontainer` submodule `4881023`;
`infrastructure` **standalone clone** `/Users/mateo/code/infrastructure` `3090f78`
(the submodule at `eden/infrastructure` is `781ee98`, and eden's recorded pin is
older still — see §7 P0-1). `iotea-archive` is at `/Users/mateo/code/iotea-archive`
and **is** readable on this machine; iotea claims below are cited, not assumed.

**Reading rule.** Every claim about existing code carries `file:line`. A claim
without one is a design proposal, not a fact.

---

## 0. The 5 findings that shape everything below

| # | Finding | Evidence |
| --- | --- | --- |
| F1 | **The org half of the domain model is already built, and it already says IOTEA.** `organizations`, `organization_members`, `permission_sets`, `accounts` are real tables with real migrations. | `apps/platformgateway/persistence/schema/schema.sql:32` "IOTEA-style multi-tenant RBAC foundation", `:40`, `:50`, `:64`, `:92`; migrations `0001`–`0004` |
| F2 | **The project half is a JSONB blob in a second service with a second database discipline.** `projects` is `id TEXT, seq BIGSERIAL, record JSONB` created by an inline DDL string — no migration, no schema, no foreign key to an org. | `apps/agentgateway/internal/projectpersistence/postgres.go:90-93` |
| F3 | **The workflow half does not exist.** Zero `Workflow` type in Go. The 10-phase pipeline is doc prose only. | `docs/architecture/04-process-model.md:20-31`; no `type Workflow` in `apps/` or `libs/go/` |
| F4 | **"eden as the template" is a configuration value, not a build.** The create-saga already clones a template repository named by config, flattens it, and pushes the seed — idempotently and resumably. | `apps/agentgateway/internal/projectcreate/projectcreate.go:76-82`; steps `saga.go:20-23`; seeder `steps.go:63-95` |
| F5 | **There is no gRPC anywhere.** Zero `google.golang.org/grpc`, zero `.proto` outside a devcontainer fixture. The API is 482 lines of OpenAPI. | `apps/platformgateway/contract/openapi.yaml`; only proto on disk is `.devcontainer/.ci/fixtures/echo.proto` |

The rework is therefore **mostly re-wiring, not green-field**. That fact drives
the simplicity law: the smallest design is the one that connects three halves
that already exist and deletes the seams between them.

### 0.1 Three corrections to the intent, measured against iotea

The intent names iotea as the reference for the environment model and the bash
discipline. iotea is readable at `/Users/mateo/code/iotea-archive`. Read, three
premises do not hold, and saying so now is cheaper than discovering it in Phase 1.

| Premise | Measured | Consequence |
| --- | --- | --- |
| "the three-env flow is the reference implementation" | **Partly.** dev/staging/production exist (`libs/bash/production.sh:12`), but **ephemeral envs, env-ids, TTL and a reaper do not exist anywhere** in iotea. Staging is one long-lived EKS cluster, `beta-staging-eks-cluster` (`deploy/infra/ctl.sh:49`), with fixed hostnames (`deploy/engine/production/ctl.sh:206`). | §3 is **eden's invention**, not a port. iotea contributes only the verb vocabulary (`create/start/stop/delete/status/list`, `services/devenv/src/*.go`). |
| "two-level infrastructure contract" | **Absent.** No `requires:`, no `kubeVersion:`, no `dependencies:`. Both `Chart.yaml` files are unedited `helm create` boilerplate — `appVersion: "1.16.0"` in both (`deploy/engine/production/Chart.yaml:24`, `deploy/services/production/Chart.yaml:24`). Layering is a bash call sequence (`deploy/engine/production/ctl.sh:885-892`). | §2 is **eden's invention**. |
| "bash written like iotea's: errors always raise … tested, catching everything" | **False as stated.** Across all 28 `.sh` files: `set -Eeuo pipefail` **never** appears (8 bare `set -e`); zero `trap ERR`; zero `die`/`log`/`warn` helpers; zero `require_cmd`/`command -v`; zero `--help`; zero `usage()` functions; zero shellcheck in CI; **zero bash tests**. `status` is the same stub string in three files (`deploy/engine/production/ctl.sh:894`, `deploy/services/production/ctl.sh:223`, `deploy/engine/test/stress/ctl.sh:70`). | The standard is **`.devcontainer/_ctl/lib.sh`**, which already has every one of those. iotea contributes eight structural conventions on top. See §4.1. |

What iotea **does** prove, and what eden must therefore do differently, is its own
deepest defect: **two hand-kept descriptions of one system** —
`deploy/engine/local/docker-compose.yaml` (306 lines) and
`deploy/engine/production/templates/*.yaml` describe the same ten services with
no shared source; the ClickHouse DDL is a parallel copy in each. eden already
generates both from one typed Go spec (`deploy/servicespec/`). §1.1 stops using
the second target; the D4 sweep removes it once k3d dev has passed its exit proof.

### 0.2 The pillar frame — round 7, and the rule it binds this plan to

Round 7 is the intent's final round and it is a **selection rule**, not a wish
list. It was absent from six drafts of this document; the header even said "the
6-round design interview". Nothing here contradicts it now.

> **Five pillars, "insanely priority, must be absolutely right BEFORE eden
> ships, because eden IS the foundation that runs inside the production
> deployment":** 1 CI · 2 INFRASTRUCTURE · 3 GITOPS · 4 AGENTS · 5 PROCESSES.
>
> **The goal: DOGFOOD.** The pillars get hardcoded → eden is created as a project
> from its own template → eden migrates onto itself → the platform develops
> itself.
>
> **The rule: "Every open task maps to exactly one pillar; work that serves no
> pillar is deferred."**

**The mapping, applied honestly — and it does not put everything in a pillar.**

An earlier draft filed all 26 items under five pillars and concluded "nothing is
deferred by round 7's rule". That conclusion was produced by widening the labels
until everything fit: eleven product items — the proto, the binary, the saga, the
board — were filed under pillar 4 AGENTS, whose named content is "review tiers,
coherence super-architect, CI instrumentation, fleet". A rule that defers nothing
and reclassifies nothing is the check that checked nothing, applied to the
intent's own final instruction.

Round 7 has **two** categories, not one, and they behave differently:

| | What it is | Ship rule |
| --- | --- | --- |
| **PILLAR work** | the five things that "must be absolutely right BEFORE eden ships" | gated — eden does not ship without it |
| **GOAL work** | the DOGFOOD chain itself: eden created from its template, eden onto itself | not a pillar; it is what the pillars exist to make possible |

| Pillar | Phase items |
| --- | --- |
| **1 CI** | P0-2 · P0-3 · P0-4 · P0-5 · P0-6 · the **#92 track** |
| **2 INFRASTRUCTURE** | P1-3 · P1-4 · P1-5 · P1-6 · P1-9 · P0-7 |
| **3 GITOPS** | P0-1 · P3-2 |
| **4 AGENTS** | — in P0–P3. Its named contents are the fleet (ledger), review tiers (#92 D2), and two components with no item at all (below). |
| **5 PROCESSES** | P1-0 · P1-7 · P1-8 |

| Goal (dogfood chain) | Phase items |
| --- | --- |
| eden exists | P1-1 · P1-2 |
| eden created from its own template | P2-0 · P2-1 · P2-2 · P2-3 · P2-4 |
| eden onto itself | P2-5 |
| the platform sees itself | P3-1 · P3-2 |

**What the rule actually defers, now that it is applied rather than asserted:**
nothing currently in P0–P3 — but **pillar 4 has no phase item**, and three of the
five pillars name components this plan neither builds nor deferred. Measured over
the document before this pass: `git-process` 0 hits, `review tier` 0,
`super-architect` 0, `instrumentation` 0, `merge condition` 0, `human gate` 0.
Each now has a ledger row with a trigger, because the document's own standard is
that a deferral is a row, never silence.

**The ship gate is all five pillars, not one.** An earlier draft gave #92 a named
cross-ledger dependency and treated the other four as satisfied by labelling. The
gate reads:

> eden does not ship until: **(1)** #92 lands, including the runner-group decision
> for the three PUBLIC repositories; **(2)** P1-3…P1-6 are green; **(3)**
> git-process v2 lands; **(4)** review tiers and the coherence super-architect
> exist, and the fleet leg has landed or been explicitly waived; **(5)** merge
> conditions and human gates are written and enforced.

Items 3, 4 and 5 are outside this plan's agent-days (§7) and inside its ship gate.
That asymmetry is the honest reading of "must be absolutely right BEFORE eden
ships" — not a reason to relabel them as done.

**The dogfood chain is this plan's spine, and P2-5 is its third link.**

```
pillars 1,2,3,5    →  eden created from its own template  →  eden migrates
   P0 + P1 + P3-2       P2-3 (TemplateRepositoryURL           onto itself
   (pillar 4 has         = gophersys/eden) + P2-4              P2-5
    NO phase item)
                                                                 │
                                       the platform develops itself
                                       ← the fleet leg, deferred with a trigger
```

**The cictl reconciliation — the one place round 7 changes an earlier ruling.**
§7 declines to fund #92 inside this plan, on grounds that hold against rounds 1–6:
it is a different, already-running program under **ledger #44**, and
double-booking it would make Phase 1 wait on unrelated work. Round 7 does not
overturn that, but it does change its status: **CI is pillar 1, and pillar 1 must
be right before eden ships.** So #92 is not out of scope — it is a **parallel
pillar-1 track with its own ledger, and a ship gate**:

> eden does not ship until #92 has landed, including the runner-group decision
> for the three PUBLIC repositories that `arc-review` refuses.

That is a dependency this document now names, rather than a refusal it leaves
implicit. It costs this plan zero agent-days and it is the honest reading of
"absolutely right BEFORE eden ships".

---

## 1. Target architecture

### 1.1 The one-product shape

```
                         ┌─ browser ────────────────────────────────┐
                         │  SvelteKit SPA (@eden/theme, primitives, │
                         │  visualization) — dense-UI framework     │
                         └──────────────────┬───────────────────────┘
                                            │ HTTPS, one origin
              ┌─────────────────────────────▼─────────────────────────────┐
              │  ingress-nginx + cert-manager  ·  oauth2-proxy · tailnet  │
              └─────────────────────────────┬─────────────────────────────┘
                                            │
   ╔════════════════════════════════════════▼══════════════════════════════════╗
   ║  edend — ONE Go binary, one image, one deploy unit                         ║
   ║  ┌──────────────────────────────────────────────────────────────────────┐  ║
   ║  │ go:embed static/  → serves the SPA. No nginx, no reverse proxy.      │  ║
   ║  ├──────────────────────────────────────────────────────────────────────┤  ║
   ║  │ grpc-gateway  (REST+JSON /v1/…)   ◄── generated ──┐                  │  ║
   ║  │ gRPC server   (:9090)             ◄── generated ──┤                  │  ║
   ║  │                                                    │                  │  ║
   ║  │            protocols/eden/v1/*.proto ── buf ───────┘                  │  ║
   ║  │            one contract → Go server, Go client, TS client             │  ║
   ║  ├──────────────────────────────────────────────────────────────────────┤  ║
   ║  │ services, each New(cfg Config, deps Deps) (*T, error)                │  ║
   ║  │   organization · project · run                                       │  ║
   ║  │ ONE role, ONE replica. Reconciliation runs in-process.               │  ║
   ║  └───────┬──────────────────────────────────────────────────────────────┘  ║
   ╚══════════│═══════════════════│══════════════════════│══════════════════════╝
              │                   ┊ NOT in P0–P3         │ installed P1-5
        ┌─────▼─────┐      ┌──────┴───────┐      ┌───────┴────────┐
        │ CNPG      │      │ NATS         │      │ object store   │
        │ postgres  │      │ JetStream    │      │ S3 API         │
        │ (schema   │      │ FLEET plane  │      │ INSTALLED P1-5 │
        │  v0, §6)  │      │ only:        │      │ barman backups │
        │  the only │      │ events ·     │      │ only; the LEG  │
        │  v0 R/W   │      │ control ·    │      │ (Go port) is   │
        └───────────┘      │ inbox        │      │ deferred       │
                           │              │      └────────────────┘
                           └──────┬───────┘
                                  │
                          ┌───────▼────────┐
                          │ eden-agent     │  the fleet: 1 pod = 1 role,
                          │ (agent pod     │  1..N harness sessions.
                          │  image)        │  Consumed as an internal service.
                          └────────────────┘
```

**One store the PRODUCT reads or writes: postgres.** The object store is a
different case and the distinction is load-bearing. An S3 endpoint (MinIO) **is**
installed from P1-5, annotated as the `objectstore` capability, probed on every
`env up`, and written to — by **barman**, taking staging's and prod's CNPG
backups (§3.4). What is deferred is the object-store **leg**: the product's own
bucket grammar, artifact addressing, inline cap and sweep, in Go, through the
`objectstorage` port. No `edend` code opens an S3 client in P0–P3.

NATS is the genuinely absent one: not installed, not annotated, not probed, and
not brought up before the fleet leg lands. Three homes for one event stream was
the largest complexity in the first draft; one home plus a backup destination is
where it settled.

**The whole fleet leg leaves the first slice, as one piece.** The dashed edges
above — NATS, `eden-agent`, and the two saga steps that need them
(`launch_supervisor`, `supervisor_ready`) — are one deferral with one trigger,
not four independent ones. Splitting them was the pass-1 defect: NATS was
deferred while the saga steps that require it stayed, so Phase 2 asserted a
supervisor reaching ready on a transport no phase brings up. See the ledger.

**One image in the first slice; two at the target.** Today the release builds
four (`.github/workflows/release.yml`, images `agentgateway`, `agent-runtime`,
`platformgateway`, `frontend`) and deploys five workloads
(`infrastructure/apps/eden/{50,52,54,56,58}-*.yaml` — the orchestrator is a
second Deployment of the agentgateway image). The target is `edend` +
`eden-agent`; **P0–P3 build and deploy only `edend`**, and the chart P1-3
writes has ONE long-running workload. `eden-agent` arrives with the fleet leg.

**One role, not two.** The intent's words are "the same binary scales BOTH axes:
goroutine pools in-process AND k8s replicas horizontally". A goroutine pool
inside `serve` is the first half; the `replicas` knob is the second. A second
entrypoint mode is a second Deployment, a second values block and a second
rollout — the fifth workload, re-created one layer down.

**And one replica, with no leader election, in v0.** An earlier draft said
"reconciliation runs in-process behind leader election" and set prod to
`replicas: 2`. No phase built, priced or proved either: P1-2 builds two muxes and
one RPC, P2-2 re-homes the saga "logic unchanged", and the Phase-2 proof tests
`kill -9` resume, not leadership. No round asks for HA — exactly one cluster, one
user. The `replicas` knob stays, so the horizontal axis stays true; its value is
1 everywhere until something measures a reason.

This also closes a gap the pair created. `PRIMARY KEY (run_id, step)` prevents a
duplicate ledger **row**; it does not prevent two un-elected drivers both
**calling** `provision_repo`. Today that is survivable by accident —
`forge.CreateRepository` is contractually idempotent (`forge.go`: *"if the
repository already exists, the existing repository is read back rather than
erroring"*) and the seeder converges (`steps.go:63-66`) — but "survivable by
accident" is not a design. One replica makes it survivable by construction, and
the ledger carries what must exist before `replicas > 1` returns.

Four images today, one in P0–P3. What removes each:

| Image today | Removed by | Evidence |
| --- | --- | --- |
| `frontend` (nginx) | the SPA is static; the Go binary serves it and the API from one origin | `apps/frontend/deploy/Dockerfile:53` `FROM nginx:alpine`, `nginx.conf` same-origin-proxies `/gateway` and `/platform` to two backends |
| `platformgateway` | folds into `edend` — one domain, one database, one auth spine | 11 124 Go lines |
| `agentgateway` | **becomes** `edend` | 23 679 Go lines; the split is why F1 and F2 disagree |
| `agent-runtime` | **the fleet deferral** — it is the agent-pod image and has no other consumer | ledger, one row, one trigger |

Separately, and not an image: the **compose renderer** stops being used in P1 and
is swept with the rest of `deploy/servicespec` by D4 (§3.4) — never in the same
change that introduces its replacement.

**Where each environment cuts.** The cut is the values profile, never the chart
and never the code. Two profiles are `env`'s; the third is Argo's.

```
 dev      │ k3d, one machine, N per-caller ids    │ profile=dev     │ ns eden-<id>
 staging  │ any compliant cluster, N instances    │ profile=staging │ ns eden-<env-id>
 ─────────┴───────────── `ctl.sh env up` ─────────┴───────────────────────────────
 prod     │ exactly ONE cluster                   │ profile=prod    │ ns eden
          │ applied by Argo CD from the promotion PR that release.yml already
          │ opens — NOT by `env up`. See §3.1.
          └──────────── SAME chart, SAME images, SAME manifests ────────┘
```

### 1.2 The per-project UI slot (layout deliberately NOT decided here)

Mateo co-designs the per-project surface later. This blueprint fixes only the
seam it plugs into. Locked now:

**Routes.** The ORGS → PROJECTS → WORKFLOWS hierarchy is three addressable
levels. It does not require three tables (§6.1).

```
/o/<org-slug>                                org home
/o/<org-slug>/p/<project-slug>               project SHELL  ← the slot
/o/<org-slug>/p/<project-slug>/w/<kind>      workflow surface
```

**The workflow level is real, and it is declared in code rather than in rows —
or in traffic, or in chrome.** `WorkflowKind` is a proto enum: a named, closed
set. P1-1 generates the TypeScript client from that same proto, so the SPA holds
the whole set at build time.

Three things carry the level, and none of them is a widget:

| The level is | Carried by |
| --- | --- |
| named | the `WorkflowKind` enum |
| addressable | the route `/w/<kind>` |
| grouped | `workflow_runs.kind`, returned by `GetProjectSurface` |

No table. No listing RPC — a call returning a compile-time constant is a round
trip that tells the client what it knows. **And no rail**: v0 has exactly one
kind, and navigation chrome between the members of a one-member set is a label.
The same argument that defers the org/project switcher below applies to the rail
on the same date, and committing one now would decide layout — which this
section's own heading reserves for the co-design. If the P3-1 co-design wants a
rail, it designs one.

**The shell owns** exactly one named outlet. The **org/project switcher** is
chrome for branches that barely exist at the end of Phase 2 — one organization,
two projects — and it lands with the P3-1 co-design that decides its layout.

**The slot owns** nothing else and fetches nothing itself.

**The project surface reads through exactly ONE RPC, and that is the lock.**

| RPC | Shape | Latency class |
| --- | --- | --- |
| `GetProjectSurface(org_slug, project_slug)` | unary → `{project, runs[]}` — runs carry `kind`, so the surface groups them without a second entity | one round trip on navigation, re-called on a poll while a run is live |

**Stated honestly: v0 ships two RPCs in total** — the one above, plus
`CreateProject`, a mutation at the *org* level that is not part of the slot's
data contract.

**There is no live stream, and the board does not need one.** An earlier draft
added `WatchProjectEvents`, a server-stream over a `bigserial` `events` table
resumable by `from_seq`. Its own implementation polled a table on a 1 s tick and
pushed the result to a client that was already calling `GetProjectSurface` — that
is client polling with a stream in the middle, and it bought a resumability
contract, an ordering authority and a reconnect story to make a row change inside
two seconds. The SPA re-calling one unary RPC does that by construction. §6.1
gives the rest of the reasoning; the leg reopens on one trigger, *the first event
producer the product does not itself perform*.

The lock is scoped to what it was always about: what the project surface
**reads**. Anything that would add a second read reopens this table.

Rule: the slot renders props. It never imports a transport. This is the
`ui-bind` adapter seam (`~/code/research-ui/framework/DENSE-UI.md`), and it is
what lets the layout change without touching the backend.

**The framework is staged and gated, and this document had been naming it as a
label.** Round 4 says the UI is "designed under the ui research framework
(boards-not-prose as a product principle)". That framework forbids a layout word
before **Gate 1** (the parameter census) passes — and §1.2 and P2-4 commit layout
(one outlet, no rail, switcher deferred) with no census anywhere. So the entry
criterion is named here rather than assumed:

| Stage | Artefact | When |
| --- | --- | --- |
| REASON | `census.md` — every parameter the project surface must show, addressed and tiered | **P3-1, before any layout word** |
| LAYERS | `layers.md` — L0→L5, ending at Gate 2 (squint · greyscale · worst-case string · point · glance) | P3-1, with Mateo |
| CONTRACT | Gate 3 drills, **run not asserted** | P3-1 |

The co-design has an entry criterion (Gate 1 passed) and an exit proof (Gate 2's
five drills, Gate 3's run). §1.2's own layout commitments are provisional until
that census exists — which is why the rail and the switcher are deferred rather
than designed. **Boards-not-prose is the product principle** the census serves:
counts, states and ages before sentences.

---

## 2. The L1 / L2 infrastructure contract

### 2.1 What already exists (do not rebuild it)

| Piece | Where | State |
| --- | --- | --- |
| 6 versioned platform contracts with front-matter `contract:`/`version:`/`fulfilled_by:` | `infrastructure/contracts/{databases,identity,ingress,messaging,observability,secrets}.md:1-5` | all `0.1.0-draft`; sections CI-enforced by `scripts/verify-structure.sh:31-73` |
| per-cluster capability declaration | `clusters/instances/<c>/identity.yaml` → `platform_services.<category>.<impl>.{enabled,version}` | homelab `:92-104`, prod `:127-137`; schema `clusters/CONVENTIONS.md:23-93` |
| a **versioned contract with a bidirectional CI check** — the pattern to copy | `providers/compute-unit/contract.yaml:17` `version: 1`; forward check `providers/oracle/modules/compute/ctl.sh:72-101`; reverse check `providers/compute-unit/ctl.sh:89-117` | working today |
| a **measured, not declared** contract — the other pattern to copy | `contracts/exposure.yaml` + `scripts/verify-exposure.sh` (resolves DNS, probes HTTP per host) | working today |
| the contract→chart value mapping | `charts/README.md:107-114` | written; templates are empty stubs (`charts/README.md:145-150`) |
| eden's requirement list, in prose | `infrastructure/apps/eden/README.md:30-61` — service DNS, vault path + field names, 4 ServiceAccounts, postgres user/db/secret names | not machine-readable, nothing verifies it |

The named gap is already on record: `infrastructure/.claude/rules/40-platform-contracts.md:72-73`
— *"Still not built: the assertion that a 'fulfills contract X' claim matches a
real file. Nothing checks it today."*

### 2.2 The design — one generated file, one annotation pair, one probe

iotea has nothing to copy here (§0.1), so this is designed from what
`infrastructure` already proves it can hold. It adds **nothing to git that can
lie**: one generated index, one annotation pair on the chart, and a probe that
asks the cluster.

**L1 — one datum, not a generated index.** `infrastructure/contracts/` gains a
single line in its `README.md` front-matter:

```yaml
capability: 1.0.0     # the contract SET's revision. Bumped by hand, by rule:
                      # any member's MAJOR or MINOR move bumps this.
```

Member versions are read **from the eight `contracts/*.md` front-matters
themselves** — they are already there (`contract:`, `version:`, `fulfilled_by:`),
already CI-enforced by `scripts/verify-structure.sh:31-73`.

**Why no `capability.yaml`.** An earlier draft generated one: an index listing all
eight member versions plus the aggregate. That is a generator with one output and
one consumer — the pattern §3.4 deletes `deploy/servicespec` for by name. Eight of
its nine values were copies of the front-matters it was generated from, which is
the only reason it needed a byte-identical drift check; delete the copy and the
check has nothing to check. The ninth value, the aggregate, is **not derivable
from its members at all** — every member reads `0.1.0` while the aggregate read
`1.0.0` — so it was a human decision living in a comment inside a file stamped
DO NOT EDIT. Round 1 asks for `requires: infra >= vX`: one number, not an index
built around it.

**Eight members, not six — L1 must cover the cluster, not only its services.**
Round 1 defines L1 as *"the cluster itself — autoscaling, nodes, namespaces,
RBAC, ALL of it — versioned as a capability"*, and round 2 restates it as *"core
set, RBAC shapes, storage classes, cert-manager, observability endpoints"*. The
six contracts that exist today are all **services**; measured on disk, none of
them mentions a storage class, RBAC, a node pool, autoscaling or a quota
(`grep -in 'storageclass|rbac|node pool|autoscal|quota' infrastructure/contracts/*.md`
→ one unrelated JetStream line). So the four properties Mateo named *first* were
outside the contract entirely.

That is not a cosmetic gap. `env up` step 3 is `helm upgrade --install`; against
a cluster with no default StorageClass it hangs on a Pending PVC — **after**
a `preflight` that returned 0. That is precisely the failure §2.2 deletes the
per-cluster `capability:` key to avoid, reintroduced one level out.

`contracts/substrate.md` (new, `version: 0.1.0`) names **five**:

| Property | What a compliant cluster provides | Already declared where |
| --- | --- | --- |
| storage | a **default** StorageClass that binds a PVC | nowhere — the gap |
| namespaces | `<project>-<env>` provisioning with a quota tier | `clusters/instances/*/identity.yaml` → `namespace_provisioning.default_quota_tier_by_env` |
| RBAC | the namespace-scoped Role/Binding shape an app's ServiceAccount receives | `infrastructure/apps/eden/20-rbac.yaml`, per-app and hand-written |
| nodes | schedulable CPU/memory for the declared quota tier | `node_role_assignments` names roles, never capacity |
| **autoscaling** | whether the cluster can GROW — a contract property, **not probed** (see §2.3) | nowhere |

**Autoscaling is in the list because Mateo put it first.** Round 1's four are
*autoscaling, nodes, namespaces, RBAC*. An earlier draft delivered storage,
namespaces, RBAC and "headroom" and claimed a 1:1 restoration — two of the four
had been silently substituted, storage borrowed from round 2's list and headroom
coined here. The substitution is not neutral: headroom is a static snapshot a
fixed cluster passes or fails, whereas growth is what makes round 1's "deployable
on k3d single-machine, full AWS, DO — same charts" true of a cloud cluster.

**Autoscaling is the one substrate property with no probe assertion**, and that is
deliberate. A draft had the probe compare a *declared* posture against reality —
which needs exactly the per-cluster declaration this section deletes two
paragraphs below ("L1 per cluster — nothing"), and which the table above records
as declared **nowhere**. A check that cannot run until the plan re-adds what it
removed is not a check. So autoscaling stays a **contract property**: the
`substrate.md` interface names it, a cluster that claims the contract states its
posture in its own README, and no assertion pretends to verify it until a
declaration exists that is not a lie. The other nine assertions ask the cluster
and compare against nothing; `nodes` is the tenth and compares against
`namespace_provisioning.default_quota_tier_by_env`, a key that already exists.

**`contracts/objectstore.md` (new) — an S3 endpoint that accepts a write.**
Staging runs `postgres.backups.enabled: true` (§3.4), and CNPG's
`barmanObjectStore` needs a live destination. An earlier draft turned backups on,
named a destination, and extended neither the capability list nor the probe — so
`preflight` returned 0 against a cluster with no backup target and `env up
--profile staging` was left to discover it at step 5. That is the identical
failure that justified adding `substrate` one paragraph above.

**Not to be confused with the deferred object-store leg.** This member is *an S3
endpoint exists and accepts a write*. The deferred leg is the product's bucket
grammar, artifact addressing, inline cap and sweep, in Go, through the
`objectstorage` port. A database backing itself up is infrastructure; the product
writing artifacts is the leg.

**L1 per cluster — nothing.** No new key in `identity.yaml`. A capability
version stored in git is a declaration, whatever the comment beside it says, and
`clusters/instances/prod/identity.yaml:3-16` is the standing proof that these
files describe clusters that are not running. A `preflight` that read such a key
would pass green against a cluster short of every contract — a check that checked
nothing, which FAIL-NOT-SKIP forbids by name. **The cluster's capability is
derived from the probe, at run time, every time.**

**L2 — one annotation PAIR on eden's chart, naming the subset eden actually uses.**

```yaml
# deploy/chart/Chart.yaml
annotations:
  gophersys.io/requires-capability: ">=1.0.0"          # the INDEX version
  gophersys.io/requires: "substrate,databases,ingress,secrets,observability,identity,objectstore"
```

Two fields, one requirement — and the second is load-bearing, not decoration.
An earlier draft cut it on the premise that a cluster provides every member,
which made a name list redundant against a version compare. **That premise is
false.** eden uses seven of the eight contracts; `messaging` is the fleet's, and
the fleet is deferred. Without the list, `preflight` would demand a NATS that
nothing in P0–P3 uses and `env up --profile dev` could never pass its own first
step.

The list is **chart-level, never per-profile** — that is what killed the
`auth.mode` knob (§3.4). So dev installs the object store too, and exercises the
same backup path staging does. Round 1 asks for exactly that: dev runs "the WHOLE
platform … backend + UI + databases + everything".

The version field says *which revision of the contract set* eden was written
against. The list says *which members must answer*. Neither substitutes for the
other.

### 2.3 The two checks — both directions, both executable

| Direction | Verb | Asserts | Runs in |
| --- | --- | --- | --- |
| **downward** — the repository's claims resolve | `infrastructure/ctl.sh verify-capability` | every `contracts/*.md` `fulfilled_by:` path resolves to a real directory | `infrastructure/.github/workflows/validate.yml` — hermetic, no cluster |
| **upward** — eden refuses a cluster that is short | `eden ctl.sh env preflight --cluster <c>` | probes the LIVE cluster for **exactly the annotated members**, compares the index version, and fails naming the capability that did not answer | inside `env up` (§3.1); **runs in eden's PR lane via P1-9, never in `infrastructure`'s** |

Seven annotated members, **ten** probe assertions — `substrate` carries four of
its five properties, the other six members carry one each:

```
substrate      a default StorageClass exists AND a 1Mi test PVC reaches Bound
               a <project>-<env> namespace can be created and carries a quota
               the namespace-scoped Role/RoleBinding shape applies
               allocatable capacity >= the profile's quota tier
databases      the CNPG CRD is registered
ingress        an IngressClass exists AND a ClusterIssuer is Ready
secrets        the secrets provider answers (ClusterSecretStore Ready)
observability  the OTLP endpoint accepts a span
identity       the oauth2-proxy Service resolves
objectstore    a bucket accepts a PUT and returns it on GET
```

The `substrate` and `objectstore` assertions are the ones that matter most and
cost least: a PVC that reaches `Bound` is four seconds, a PUT/GET round trip is
one, and each is the difference between a `preflight` that means something and an
`env up` that fails at step 5 with the cluster half-built.

The **bring-up is the probe's other half, not a third check.** `helm install
--wait` of `infrastructure`'s capability substrate (P1-5) cannot return 0 unless
those members are present. One artifact, described once: the developer's cluster
and the probe target are the same object, so what is verified is what people run.

**Why the probe is not in `infrastructure`'s CI — and why it IS in eden's.** The
policy is `infrastructure`'s, and it is twice-written with its reason in place:
`.github/workflows/validate.yml:68-72` — *"it would make it fail for the
environment rather than for the property, and the fix for that is always a
skip"* — repeated for the admission guard at `:121-123` and codified as
"LOCAL-ONLY VERBS" at `ctl.sh:203`. Building a k3d cluster on every
`infrastructure` pull request would also be the second build of a cluster
`env up --profile dev` already builds.

eden's lane is the opposite case, and P1-9 puts the probe there deliberately. A
`pr-env.yml` exists to answer *"can this pull request get an environment?"* — so
a cluster that is short of a capability is **not** an environment failure
standing in for a property; it **is** the property, and a red run naming the
missing capability is the correct answer rather than a flake. The earlier draft's
unqualified "not a PR gate" was written when only two callers existed and was not
re-read after the third was built.

**Tempted, not taken:** a capability *registry service*, a generated index of the
member versions, per-capability semver ranges, a conformance CRD, and a
`capability:` key per cluster. One generated
file, one annotation pair and one probe make the claim falsifiable. Grow it when
a second consumer exists.

---

### 2.4 `secrets` — the member that had no consumer, and the Vault it displaces

`secrets` is annotated, probed and installed, and for one draft **nothing
consumed it**. That is the one thing §2.2's member rule forbids: the list says
which contracts must answer, and `messaging` is excluded precisely because its
consumer is deferred. A member with no consumer is either dead weight or a
missing chart object. It was the second.

**It is a missing chart object, and the object is an `ExternalSecret` carrying
exactly one payload.** P1-3 creates it for barman's `s3Credentials`:

| Materialised | Consumed by | Without it |
| --- | --- | --- |
| barman `s3Credentials` | the CNPG `Cluster`'s `barmanObjectStore` | `postgres.backups.destination` names a bucket the cluster cannot authenticate to |

**The database DSN is NOT in it, and that was a second home for a credential the
operator owns.** CNPG generates a `<cluster>-app` Secret when it reconciles the
`Cluster` object P1-3 already ships — host, user, password, dbname and a
ready-made connection URI — and it rotates it. `edend` reads that. An
`ExternalSecret` duplicating it could diverge from the operator's copy, which is
iotea's deepest defect (§0.1) at credential scale. Only the S3 keys are genuinely
external.

**A consequence worth stating: in dev the `ExternalSecret` has no payload at
all**, because dev backups are off (§3.4). The object is still templated and the
`secrets` capability is still probed — dev exercises the provider, not the
secret. That is the honest shape, not a hole.

**And it displaces Vault, which the plan was archiving without saying so.** The
two facts collide on disk: `infrastructure/contracts/secrets.md` is fulfilled by
**External Secrets Operator backed by Bitwarden**, while eden's live surface is
Vault-deep — `EDEN_VAULT_MODE=token-file`, `VAULT_ADDR`, a mounted
`eden-vault-token`, and `vault://eden/<stage>#<field>` references
(`infrastructure/apps/eden/README.md`; `deploy/servicespec/catalog.go`). D4
archives `deploy/plane/local/`, which is the only Vault dev has today. So the
plan removed one provider, installed another, and scheduled nothing to reconcile
them — while round 1 names *"vault access"* as a property of daily interactive
dev sessions.

The reconciliation follows the contract, so it is not a new decision: **an app
declares its needs and the platform fulfils them** (`contracts/README.md`). eden
declares `secrets`; the platform's `secrets` is ESO/Bitwarden; therefore `edend`
reads projected Secret keys, not `vault://` references. What P0–P3 migrates is
what P0–P3 uses: **the DSN and the barman credentials.** The rest of eden's Vault
surface — the connectors KEK, harness credentials, the per-team connector store
(ADR-0029) — belongs to the fleet leg and is deferred **with** it, on the same
trigger, rather than half-migrated now.

## 3. The environment machinery

Ephemeral environments do not exist in iotea (§0.1). The verb vocabulary is the
one thing to lift: `create/start/stop/delete/status/list` from its per-user
devenv service (`services/devenv/src/*.go`) — and note that even there **nothing
reaps**: instances live until a human stops them.

### 3.1 The verbs — one code path for humans, agents and CI

`ctl.sh env <verb>` in eden, nx-wrapped in the monorepo (`nx run eden:env -- up …`).

```
env up   --profile dev|staging [--id <env-id>] [--ttl <duration>] [--cluster <name>]
env stop --id <env-id>                  # keep state + id, release compute
env start --id <env-id>                 # resume where stop left it
env down --id <env-id> | --expired      # --expired: the reap step + the CI lane
env ls
env preflight --cluster <name>          # §2.3, also the first step of `up`
```

**Stopping is not deleting.** Round 1 lists four operations by name — "Spin-up,
spin-down, debugging, **STOPPING** staging" — and calls cost and time
optimization "of the utmost importance". A staging instance that can only be
destroyed cannot be debugged tomorrow. `stop` scales the release to zero replicas
and suspends the CNPG cluster; the namespace, the volumes, the hostname and the
env-id survive. `start` reverses it. The TTL clock keeps running while stopped —
a forgotten stopped environment still costs storage — so `down --expired` reaps
stopped instances too.

**Six verbs, two profiles.** `up` is idempotent. Its ordering is **not uniform
across profiles**, and saying it was made the verb impossible to execute: a
`preflight` that "refuses before touching anything" cannot be step 1 on a laptop
with no cluster, and the capabilities it asserts are installed by the very
command it was supposed to precede.

**dev — a two-step BOOTSTRAP prelude, because dev owns its cluster:**

```
0a. ensure the k3d cluster exists      (create if absent — idempotent)
0b. ensure the substrate is installed  (infrastructure's bring-up, --wait;
                                        this IS the downward probe, §2.3)
```

**staging — no prelude.** The cluster is long-lived and its substrate is Argo's;
`up` never creates either.

**Then the four common steps, in order, for both profiles:**

1. `preflight` — probe the LIVE cluster against the annotation. Refuse before
   installing the release. (After 0a/0b in dev, so it is asserting what the
   bring-up just claimed to deliver — which is the point of running both.)
2. mint or accept an env-id.
3. `helm upgrade --install eden-<env-id> deploy/chart -f values-<profile>.yaml`
   into namespace `eden-<env-id>`.
4. stamp the TTL, then wait for readiness and print the URL. Non-ready is a
   non-zero exit.

`down` deletes the namespace and the Helm release. `--expired` selects every
expired namespace instead of one id — a selector on the destructive verb, not a
second verb. One deletion path is one place to make loud. `ls` reads the cluster,
never a local file — a list from a file is a list of what someone meant to create.

**Production is not an `env` profile.** eden already has a working, digest-pinned,
human-gated production path, end to end: `release.yml:240-276` builds and pushes,
then `.ci/pin-eden-digests.sh:1-10` opens a promotion pull request into
`gophersys/infrastructure`, which Argo CD reconciles with `selfHeal: true,
prune: true` (`platform/services/gitops/registry/app-eden.yaml`). **That pull
request is the intent's "deploy ALWAYS requires human approval"** — it exists, it
is reviewed and it is auditable. A `helm upgrade --install` aimed at the one
cluster Argo owns would be a second deploy mechanism, and `selfHeal` would revert
it. So the chart becomes the `source` of that same Argo Application — the registry
already runs Helm-source Applications
(`registry/app-external-secrets.yaml:15-26`). Same chart, same values file;
Argo applies it, not `env`.

### 3.2 env-id minting

**The purpose IS the id.** `pr142`, `mateo`, `agent91bb04`. No random suffix.

- ≤ 20 chars, `[a-z0-9]`, from `--id` or derived: the PR number in CI, `$USER`
  interactively, the agent id for a fleet agent. Each of those is already unique
  per caller, which is why the suffix bought nothing.
- **A collision converges; it does not refuse.** A second `up` for `pr142` is a
  `helm upgrade` of the existing release — which is what §3.1 means when it says
  `up` is idempotent. A random suffix contradicted that directly: it would have
  minted a second namespace, a second Postgres and a second cost line for the
  same pull request, which is the exact leak round 1 names as the thing to avoid.
- The id is the namespace suffix, the Helm release suffix and the DNS label:
  `eden-<env-id>` / `eden-<env-id>` / `<env-id>.eden.<domain>`.

Dropping the suffix also drops the CSPRNG, the collision-detection branch and the
63-character DNS-label arithmetic that justified its width.

**Dev mints too, and that is not a special case — it is the reason minting
exists.** Round 1 names two users of dev, and the first is *"agents in parallel
workflows"*, with agents granted *"full access to their OWN dev or staging
instances as they wish"*. An earlier draft said "`dev` keeps its own fixed id;
only staging mints", which quietly funnelled every parallel agent onto ONE
namespace and ONE hostname — where `up`'s convergence, correct for a re-run of
`pr142`, becomes data loss for two agents on two branches.

So `--profile dev` takes `--id` exactly as staging does, defaulting to `$USER`
interactively and to the agent id for an agent. Namespace `eden-<id>`, host
`<id>.dev.eden.<domain>`.

**One k3d cluster per machine, N namespaces inside it.** The substrate (§3.5) is
installed once and shared; only the eden release is per-id. N clusters on one
laptop would be the heavy answer to a question the namespace already answers.

### 3.3 TTL and the reaper

The TTL lives in exactly one place — a label on the namespace:

```yaml
metadata:
  labels:
    eden.gophersys/env-id:  pr142
    eden.gophersys/profile: staging
  annotations:
    eden.gophersys/expires-at: "2026-08-27T18:00:00Z"   # RFC 3339, UTC
```

`env down --expired` lists namespaces with the label, compares `expires-at` to
now, and deletes each expired one. **It has no CronJob.** It runs from the two
callers that already hold the toolchain: as a **reap step at the top of `env
up`** (every spin-up pays for the last one's leftovers) and as a **scheduled CI
lane** against the staging host cluster. Defaults:
staging 48 h, **dev 24 h**, `--ttl` up to 7 d, `--ttl 0` opts out; a namespace
with no annotation is skipped.

**Dev is not exempt.** Round 1 puts cost "of the utmost importance across all
infrastructure **and dev** environments", and §3.2 mints one dev namespace per
parallel agent — each holding a CNPG cluster and its PVCs — on ONE laptop. PR
envs get automatic teardown (P1-9) and staging gets the scheduled lane; leaving
agent dev envs with neither was an oversight. So dev stamps a **24 h TTL** by
default (`--ttl 0` opts out), and the reap step at the top of `env up` collects
expired dev namespaces on the next spin-up — on the machine where they were made,
by the tool that made them.

**Why no CronJob.** An in-cluster CronJob running `ctl.sh env down --expired`
needs an image carrying bash, kubectl, helm and eden's scripts. §1.1 fixes P0–P3
at building only `edend`, so no phase builds it; a stock kubectl image with an
inlined script would break this section's own invariant that the reaper is **the
same code path a human runs**. An earlier draft booked the CronJob at zero on the
words "no new component" — true of the object, false of its image. Both surviving
callers already run inside the devcontainer or a CI runner, so the mechanism
costs nothing new and there is exactly one deletion path.

The TTL default lives beside the profile **in `env up`**, not in the chart
values. A values key the chart never consumes is a knob that can be set,
believed, and have no effect.

Deleting is loud, and cheaply so: a log line naming the env-id and the age, plus
the Kubernetes Event that namespace deletion emits for free. **No database row.**
The env verbs are bash with a kubeconfig — they hold no connection string, and
Phase 1 must be provable before any product schema exists. A silent reaper is a
mystery generator; a reaper that needs a database is a phase-ordering deadlock.

### 3.4 One chart, three profiles, six knobs (two applied by `env`)

`deploy/chart/` is the only chart, and it is **hand-maintained** — a first-class
artifact, not a generated one.

**The generator lost its reason when the second target died.** `deploy/servicespec`
exists because ONE typed Go spec fed TWO renderers, so the compose file and the
Helm templates could not disagree (`servicespec.go` says exactly that) — the fix
for iotea's deepest defect (§0.1). D4 sweeps the compose target and §1.1 fixes
the P1 chart at ONE long-running workload. What is left is one source rendering one
output for one Deployment: every values change would cost an edit in Go, a regeneration and
a generated-code drift check, to produce YAML that Helm values already
parameterise. A generator with a single consumer is indirection, not a shared
source of truth. This is complexity the cuts themselves created, and removing it
is the same move that justified the generator in the first place.

**The trigger that brings it back**, stated so the deletion is reversible: a
**second render target**. Not a second workload — the fleet leg adds
`eden-agent` to the same chart and that changes nothing. Nothing in the plan
schedules a second target.

Values files carry the whole environment axis. `env` applies dev and staging;
Argo applies prod (§3.1).

| Knob | dev | staging | prod (Argo) | Why it is the knob |
| --- | --- | --- | --- | --- |
| `replicas` | 1 | 1 | **1** | `stop` sets it to 0; >1 needs the ledger's lease row |
| `resources` | none | small | measured | |
| `postgres.backups.enabled` | false | **true** | **true** | round 3: **dev ephemeral** |
| `postgres.backups.retentionDays` | — | **7** | 30 | **the compactness lever** |
| `postgres.backups.destination` | — | the homelab MinIO bucket | the Oracle bucket | round 3 names both |
| `ingress.host` | `<id>.dev.eden.<domain>` | `<env-id>.eden.<domain>` | `eden.<domain>` | |

**Six knobs, down from ten.** Cut for having no measurement behind them:
`observability.traceSampleRatio` and `observability.logsToLoki` (sampling and
shipping are the collector's properties, and the substrate's `observability`
capability supplies the endpoint — the chart just emits to it); `nats.jetstream.maxBytes`
(NATS is the fleet's and is not installed, §1.1); `objectStore.retentionDays`
(the S3 endpoint **is** installed and written to, by barman alone — and barman's
retention is `postgres.backups.retentionDays` one row above, so a second key
would be a second home for one policy; it returns with the object-store leg and
its first non-barman writer); `ttl.default` (a second home for a value §3.3
declares single-homed).

**`auth.mode` is gone too, and it should never have been added.** It was written
as dev=`tailnet`, staging=prod=`oauth2-proxy`, which makes the two an either/or —
the exact reading D1 rejects on the record ("tailnet **+** oauth2-proxy — two
layers, not a choice between them"). It also fought the rest of the design: the
chart annotation requires `identity` at chart level, `preflight` probes that the
oauth2-proxy Service resolves on **every** `env up` including dev, and §3.5
installs it in the dev k3d cluster. A dev value that routed around a layer the
same profile installs and probes is dead weight in one direction or the other.
**oauth2-proxy stands in front in all three profiles**; reachability stays where
D1 already puts it — the `ingress.host` domain. Dev then exercises the same auth
path staging and prod use, which is round 1's "best balance between development
speed and thorough testing/QA", not a cost against it.

**Staging is compact by RETENTION, not by amputation.** Round 1 gives both halves
in one sentence: staging is *"COMPACT: full features (observability, backups) but
with a configurable retention (~7 days) so it does not eat resources. A
pre-production balance, not costly."* An earlier draft achieved compactness by
switching backups off and dropping observability — which would have made staging
unable to serve round 1's own promotion rule, that a human "inspects the staging
that is to be released" and does QA on it. Backups are **on** in staging;
observability comes from the substrate; 7-day retention is what keeps the bill
small.

**Backups now have a target, a retention that says what it retains, and a probe
that checks the target exists.** Three seams closed together, because they were
one seam:

- **`retentionDays` is `backups.retentionDays`.** It is barman's base-backup + WAL
  retention, and nothing else. Unqualified, it read as if it might prune `events`
  rows — which nothing does — and it sat at `1` in a profile that had backups
  switched off, making it settable, believable and inert: the exact test that cut
  `ttl.default` one paragraph below.
- **`destination` is a knob, not a hard-coded string.** It has to be, because its
  value differs per profile. Round 3 already names both ends — "MinIO in
  dev/staging, Oracle bucket (S3 API) in prod" — so the knob **cites the intent
  rather than pre-answering an open question**. (An earlier draft called prod's
  destination "still an open ledger question". It is not: the retired decision was
  about the *product's* object store, and round 3 settled the datastore itself.)
- **`enabled` is FALSE in dev.** Round 3 fixes dev's posture by name: "CNPG
  operator everywhere (**dev ephemeral**, staging 7d-compact, prod full
  backups→Oracle bucket)". An earlier draft turned dev backups on by analogy with
  `auth.mode`, and the analogy is false: `auth.mode=tailnet` routed request
  traffic *around* a layer the same profile installed, whereas `enabled: false`
  bypasses nothing — the annotation is still chart-level, §3.5 still installs
  MinIO in dev, and `preflight` still runs the `objectstore` PUT/GET on every
  `env up --profile dev`. Only barman goes unexercised. The cost was real and
  landed where round 1 says cost matters most: §3.2 mints one dev namespace per
  parallel agent on ONE laptop, so it meant continuous WAL archiving and a
  base-backup schedule, N times over, on a developer machine.

What this is **not**: the deferred object-store *leg* — the product's own bucket
grammar, artifact addressing, inline cap and sweep, in Go, through the
`objectstorage` port. A database backing itself up to an S3 endpoint is
infrastructure configuration. The two were conflated, and conflating them is what
made round 1's "full features … with a configurable retention" look unaffordable.

**`events` growth is bounded by the reaper, not by this knob.** A staging instance
dies at its TTL, so its event rows die with it. Prod's `events` table grows
without bound in v0; that has a ledger row with a trigger, and it is honest to say
so here rather than let "retention" imply a pruning nothing implements.

**Cost control is a schedule, not a hope.** `env ls` prints **age, state and
profile** per instance; `stop` releases compute without losing state; `down
--expired` enforces the TTL; `postgres.backups.retentionDays` bounds the backup
storage a long-lived staging can reach.

An earlier draft had `ls` print a "cost class". Nothing in the design measures
one: §3.3 deliberately gives the env verbs no database and no connection string,
and no billing or metering source appears in P0–P3, so the column could only
restate `profile` — which the namespace label already carries. A printed figure
with no producer is the class of thing that gets believed, which is the failure
§2.2 rejects by name.

**Avoid iotea's values-file design.** Staging and production there share ONE file
and differ by two `--set` flags, while the file itself hardcodes
`ENVIRONMENT: "production"` (`deploy/engine/production/values/eks.yaml:13`) and
is overridden at deploy time. The file lies about itself. Three files, each true,
cost nothing. Three of its four declared values files never existed at all
(`deploy/services/production/ctl.sh:75-78`), and the branch that reads them is
unreachable because `$CONFIGURATION` is never assigned (`:84`).

### 3.5 Dev: k3d running the real thing

Today dev is docker-compose of the *supporting* services plus host processes
(`deploy/ctl.sh:31`, `deploy/plane/local/docker-compose.yaml` — Vault, NATS,
Postgres only). The intent is the whole platform on one machine, iotea-style.

The tools are already pinned and installed and **completely unused**: k3d 5.9.0
(`.devcontainer/versions.env:153-155`), kind 0.32.0 (`:156-158`), helm 4.2.4
(`:147-149`), kubectl 1.36.3 (`:144-146`). The audit found **no script anywhere
in `.devcontainer` that creates a cluster**.

So: `env up --profile dev` creates a k3d cluster if absent, calls
**`infrastructure`'s capability bring-up**, then installs the SAME
`deploy/chart`. Docker comes from the socket the devcontainer already mounts
(`.devcontainer/base/ctl.sh:180`, stated purpose at `:154-155`: *"so the
k3d/kind/docker integration + load lanes work from inside"*).

**The substrate belongs to `infrastructure`, not to eden.** A capability provider
living in `eden/deploy/` inverts the contract it exists to satisfy —
`infrastructure` is the named L1 capability registry (round 2). And §2.3 needs
exactly the same artifact for its probe, so building it in both repositories is
the second-truth failure this document forbids two sections earlier. One
bring-up, in `infrastructure`, serves both: it is the dev cluster *and* the probe
target, so what is verified is what developers run.

**The substrate installs the six SERVICE capabilities, and no more** — the
seventh annotated member, `substrate` itself, is the cluster's own and is
asserted rather than installed. A `helm install --wait` of pinned upstream
charts for `databases` (CNPG),
`ingress` (ingress-nginx + cert-manager), `secrets`, `observability` (an OTLP
collector), `identity` (oauth2-proxy) and `objectstore` (MinIO), on a k3d cluster
whose `substrate` members k3d supplies natively — local-path is the default
StorageClass; namespaces, RBAC and capacity are the cluster's own; and its
autoscaling posture is honestly declared `fixed`. Round 1 is not negotiable on
this: dev runs *"the WHOLE platform as a single-instance deployment on one
machine — backend + UI + databases + everything"*, in *"daily interactive
sessions (with vault access)"*. A two-capability substrate would have been a dev
environment that boots nothing and a `preflight` that can never pass.

**Not** `messaging` — NATS is the fleet plane, and the fleet leg is deferred as
one piece (§1.1). **MinIO IS installed** — as the `objectstore` capability, the
S3 endpoint CNPG backs up to (§3.4). What stays deferred is the object-store
*leg*: the product's bucket grammar and `objectstorage` adoption in Go. NATS
re-enters the substrate with the work that first consumes it, and the chart
annotation is what records that it is not required yet.

### 3.6 The develop/test seam — round 2's named "current big problem"

Round 2 states it in Mateo's words: *"cleanly separate develop and test without
losing speed or adding complexity. We really have to create really clean
abstraction layers."* Every earlier draft of this document failed to mention it —
and made it worse without noticing, by archiving `deploy/plane/local/` (today's
fast loop is compose plus host processes), refusing Tilt and Skaffold, and
replacing the loop with `k3d + substrate + helm upgrade`. A `helm upgrade` per
edited Go file is a minute; the loop it replaces is two seconds.

**The abstraction is that the loop is not a deployment.** Two runtimes, one
configuration contract:

```
   INNER — ctl.sh dev                      OUTER — ctl.sh env up --profile dev
   ────────────────────                    ──────────────────────────────────
   edend runs on the HOST                  edend runs in the cluster
   go run  ·  vite dev + HMR               real image · real chart · real ingress
   port-forwards to the substrate          in-cluster DNS to the substrate
   ~2 s Go · ~50 ms Svelte                 ~60 s
   deploys NOTHING                         the artifact CI and the proofs use
                    │                                    │
                    └──────────┬─────────────────────────┘
                               ▼
                    values-dev.yaml  →  the SAME variable names
                    `configuration` parses at the edge (§5)
```

**What makes this one truth rather than two.** The inner loop does not carry its
own configuration: `ctl.sh dev` PROJECTS its environment from `values-dev.yaml`,
the same file the chart renders, into the same variable names the `configuration`
library parses once at the edge. A knob added to the chart reaches the inner loop
without being written twice. That projection is the abstraction layer Mateo asked
for; it is also, exactly, what iotea did — compose for the services, host
processes for the application.

The substrate is shared: both runtimes talk to the same CNPG, MinIO, OTLP and
oauth2-proxy in the same k3d cluster. Only where `edend` executes differs.

**Proven by measurement, not by claim** (P1 exit proof): edit one `.go` file and
observe the change served in under 5 s; edit one `.svelte` file and observe it in
under 1 s. A loop nobody timed is a loop nobody will use.

**Tempted, not taken:** a separate `dev` chart, a compose fallback, Tilt/Skaffold,
and an eden-owned substrate umbrella. One chart is the point; one bring-up is the
point; and the inner loop earns its place by deploying nothing at all.

---

## 4. The toolchain layer

### 4.1 The standard already exists — write it down, do not invent it

Per §0.1, iotea's bash does not carry the safety half. `.devcontainer/_ctl/lib.sh`
does, with a measurement behind each rule, and it is **a submodule of every
repository already**. That is the seam. Promote `_ctl/lib.sh` to the shared bash
library every repository sources, and the standard stops being a document anyone
can drift from.

The written standard is **C1–C10 (safety, from `.devcontainer`) + I1–I7
(structure and operations, from iotea) + V1–V5 (the common verb vocabulary,
§4.2)**. No part is sufficient alone: C governs how a script fails, I governs how
it reads, V governs what it is called — and `nx affected` selects on V.

The ten safety rules, each already in force:

| # | Rule | Home |
| --- | --- | --- |
| C1 | `set -Eeuo pipefail` + `IFS=$'\n\t'` in every script, tests and fixtures included | `_ctl/lib.sh:52-53`, `ctl.sh:15-16`, fixtures too |
| C2 | **No `EXIT` trap.** Measured: with the trap, a script that aborts on an unbound variable exits **0**; without it, 1. | `_ctl/lib.sh:1409-1422` |
| C3 | `main()` at the bottom, `case` dispatch, unknown verb prints usage and exits 1, `main "$@"` last line, `shift \|\| true` under `-u` | `ctl.sh:699-718` |
| C4 | three `printf` loggers, never `echo`; warn/error to stderr; defined once | `_ctl/lib.sh:171-174` |
| C5 | **FAIL-NOT-SKIP.** `require_cmd` exits **127** naming the tool. A check that opened zero files is a failure. | `_ctl/lib.sh:195-206`; zero-file failures at `ctl.sh:502-505`, `:421-424`; `_ctl/tests/harness.sh:127-131` |
| C6 | guards fail closed and every refusal names the value **and** the remedy | `_ctl/lib.sh:223-239` |
| C7 | never let `errexit`+`pipefail` swallow a diagnostic — capture the status, keep stderr | `_ctl/lib.sh:254-265` |
| C8 | never pipe a haystack into `grep -q`; use a herestring (EPIPE turns a true assertion red at random) | `_ctl/tests/harness.sh:70-101` |
| C9 | required inputs asserted with `: "${VAR:?message}"` at the top, before any work | `_ctl/lib.sh:55`, `:1887`; `_delta/components/agents.sh:21-23` |
| C10 | bodies live **once**, in the library; a per-unit `ctl.sh` sets data, sources, dispatches. Executable bit enforced. | `.devcontainer/.claude/rules/00-identity.md:92-98`; `ctl.sh:74`; `_ctl/tests/dispatcher-mode.test.sh` |

Two more that belong in the written standard because they are the difference
between a check and a ritual: comments carry **measurements and run ids**
(`ctl.sh:159` "run 32111944450"), and tests are hermetic by construction —
stub binaries first on `PATH`, `mktemp` trees of copies never symlinks
(`_ctl/tests/toolchain-parity.test.sh:55-58`).

The seven iotea conventions that `.devcontainer` does not carry, and that make a
900-line operational script readable. (An eighth was designed and withdrawn:
iotea's production gate — a red banner requiring the literal word `yes` — governs
a code path §3.1 deletes. eden deploys production from a pull request, not from
bash, so no script in P0–P3 needs it. The residue it exposes — that no rule
attaches a confirmation to `env down`, the destructive verb eden *does* have — is
a ledger row, not a smuggled restoration.)

| # | Rule | Home in iotea |
| --- | --- | --- |
| I1 | **`main()` reads as a table of contents** — each verb's body is a list of named function calls and nothing else | `deploy/engine/production/ctl.sh:885-892` |
| I2 | **Section banners at a fixed ruler**, title right-aligned, each section opening with its own constants block. Nine of them carry 917 lines. | `deploy/engine/production/ctl.sh:164-166`, sections at `:14,:19,:43,:72,:164,:672,:724,:766,:869` |
| I3 | **Visibility sigils**: `lib_` exported · `_` file-private · `__` section-private | `production.sh:6`; `ctl.sh:407`; `ctl.sh:272` |
| I4 | **Three-line function header**: purpose / `Usage:` / `Returns:` | `libs/bash/production.sh:20-23` |
| I5 | **Check-then-act idempotency, in BOTH directions** — create and teardown mirror each other exactly; a partially-deployed release resumes rather than failing | `ctl.sh:50-59` vs `:61-70`; resume at `:564-572` |
| I6 | **Named timeout constants and a mandatory `--wait`** on every cluster call. No helm invocation in iotea omits it. | `ctl.sh:27-29`, `:829-831` |
| I7 | **Root discovery by marker file**, never a counted `../../..` | `libs/bash/source.sh:3-25` |

I7 comes with iotea's own bug attached, and eden must not inherit it:
`libs/bash/source.sh:18` checks `$?` after an assignment, so the guard can never
fire; and every consumer still sources by a hand-counted relative depth
(`deploy/infra/ctl.sh:7` two levels, `deploy/engine/production/ctl.sh:7` three,
`deploy/engine/test/stress/ctl.sh:7` four). Move a script and it breaks.

eden's own `ctl.sh` files already follow C1/C3/C4/C5 (`eden/.ci/ctl.sh:11-38`).
The gap is that each repository re-declares them. Sourcing the submodule's
library closes it.

### 4.2 Standalone and monorepo-driven, coexisting

Two rules make both work with no duplication. The first governs a target's
**body**; the second governs its **name**. Only the pair is sufficient.

> **R-BODY — `ctl.sh` is the implementation. `nx` is a scheduler. A
> `project.json` target contains exactly one command: `bash ./ctl.sh <verb>`.
> Logic in a `project.json` is a defect.**
>
> **R-NAME (V1–V5) — target names are drawn from ONE closed set,
> `validate` · `build` · `test` · `lint` · `typecheck`, and each project declares
> the subset its LANGUAGE CLASS owes. A project never invents a sixth name for an
> existing concept, and never declares a target it cannot really run.**

**R-NAME is the half round 2 asked for that an earlier draft did not write
down**, and a later one over-built. C1–C10 and I1–I7 specify dispatch mechanics —
`case`, `usage`, `main "$@"` — and say nothing about which verbs exist, so the
mechanism Mateo named as the coordination layer ("**Common verbs**, simple clean
style, TRUE abstraction layers") was unspecified.

**The class table is the rule.** `validate` is universal and carries C5 — absent
tool is exit 127, never a skip.

| Class | Owes |
| --- | --- |
| Go module | validate · build · test · lint |
| TypeScript package | validate · build · test · lint · typecheck |
| bash / config unit | validate · test |

**Why not all five everywhere.** An earlier draft required every project to
declare all five and to expose an inapplicable one as "a verb that exits 0 having
said why". That manufactures ~200 no-op targets whose steady-state output is a
green that ran nothing — the advisory-step pattern FAIL-NOT-SKIP bans, installed
at 56 sites by a document that cites FAIL-NOT-SKIP eleven times. Its premise was
also wrong as an nx mechanic: **`nx affected -t <target>` skips projects that do
not declare the target**, so cross-project selection never required universal
declaration. The property that actually matters — a lane knowing which projects
OWE which target — is carried by the class table alone. `typecheck` is meaningful
for the four TypeScript packages and inert for the ~50 Go and bash ones.

Verbs beyond the set are a project's own business — `env`, `phase-gate`,
`lib-gate`, `release-check` — and nx may drive any of them. `ctl.sh verbs --check`
asserts the class table: every project declares what its class owes, and declares
nothing it cannot run (P0 exit proof).

R-BODY is already the practice — `apps/platformgateway/persistence/project.json:9,13`
is two `nx:run-commands` wrappers over `bash ./ctl.sh`. Together they give:

- **standalone** — a submodule's own CI runs `bash .ci/ctl.sh <verb>`; no nx,
  no node, no workspace. `.devcontainer/.claude/rules/00-identity.md:79-80`
  records that `.devcontainer` has no Nx workspace at all and still exposes nx
  targets that shell to `ctl.sh`.
- **monorepo** — `nx affected -t <target>` selects the projects and calls the
  same scripts. **nx owns cross-project sequencing** (set the kube context →
  deploy → update the load balancer, `iotea deploy/engine/project.json:125-137`,
  with `"parallel": false` at `:98` enforcing the order); `ctl.sh` owns one
  project's own work. That division is the part of iotea worth copying whole.

**One precondition, and iotea proves it is not free.** iotea's duality does not
exist: six of its nine `ctl.sh` hard-depend on `libs/bash/source.sh`, which walks
up looking for `nx.json` and exits if it is absent (`libs/bash/source.sh:5-6`).
An extracted `ctl.sh` fails immediately at "Could not find workspace root". So:
**the shared library must never require the monorepo.** In eden it comes from the
`.devcontainer` submodule, which is present in a standalone clone by
construction. Marker file: `.devcontainer/_ctl/lib.sh` itself, not `nx.json`.

Avoid iotea's inversion too — `services/devenv/tests/ctl.sh:69-79` calls
`nx …` from inside a script that `nx test devenv` invoked, with
`--skip-nx-cache` on every line. A cycle, and an admission that the cache model
does not fit side-effecting targets. **`ctl.sh` never calls `nx`.**

**One correction the rule forces immediately.** `eden/.ci/ctl.sh` currently
treats a missing nx as a reason to succeed. **Ten verbs** return 0 when nx is
absent — `:93-94`, `:101-102`, `:109-110`, `:117-118`, `:124`, `:129`, `:134`,
`:145`, `:159`, `:173` — and `cmd_validate` warns at `:86` then prints
`log_success` at `:88` having run only shellcheck. That is C5 inverted: the gate
reports OK when its tool is missing. Fix: `require_cmd` semantics — no nx is exit
127. (The #92 proposal names 4 of these; the true count is 10 plus `validate`.)

Also dead: `.ci/ctl.sh:45` `if [[ -z "$NX_BASE" ...` can never be true, because
`${NX_BASE:-origin/main}` at `:44` already substituted for both unset and empty.
The all-zeros arm on the same line is live and correct.

And `libs/.ci/ctl.sh:120-123` returns 0 when the affected set contained no
gateable project — so a pull request touching only `.ci/`, `templates/`,
`plugins/` or `go/_ctl/` **exits green having run nothing**, including changes to
the gating machinery itself.

### 4.3 How a tool update moves cohesively

The `.devcontainer` pins ARE the fleet toolchain. The chain exists end to end and
breaks at exactly one link.

```
_build/upstreams.txt ──weekly──► _build/resolve-upstream.sh ──► ONE bump PR
        (62 rows, 12 datasources)     (weekly-bumps.yml:68,150)
                                              │
                                     versions.env  (95 pins, one home)
                                              │
                              versions_env_build_args (_ctl/lib.sh:151)
                                              │
                                   6 images built + smoke-gated
                              (.ci/smoke.sh:187-241 — every pin classified,
                               asserted pins compared against the built image)
                                              │
                                   ghcr.io/gophersys/<image>:latest
                                              │
              ┌───────────────────────────────┴──────────────────────────────┐
              │ local devcontainer (arm64 variant)   CI runner (amd64 variant)│
              │  devcontainer.json — MUST be :latest, digest ref is REFUSED   │
              │  (ctl.sh:469); set-equality both ways with images.yaml        │
              │  (ctl.sh:430-435, :446-453); self-reference (:472-474)        │
              └───────────────────────────────┬──────────────────────────────┘
                                              │
                                   ✗ BREAK: propagation to a consumer repo
                                     is a MANUAL submodule pointer bump
                                     (.claude/rules/00-identity.md:1578-1594)
                                     and NOTHING verifies that a consumer's
                                     runner image matches its declared toolchain
```

**The diagram's two claims both stand.** Propagation to a consumer really is a
manual submodule bump, and nothing really does assert that a consumer's runner
image matches its declared toolchain. Both remain open, and both are in the
ledger — S1 and S2 — with the condition that reopens each. P0–P3 do not need
either closed: the actual Phase-0 need is one command,
`git submodule update --remote` for three pointers, judged by the gates that
already exist.

A **third** repair was designed and then withdrawn, because the reconciler it
proposed **already exists**. `.devcontainer/_build/upstreams.txt:118-127` gives
the three harness pins the `eden-manifest` datasource with coordinate
`gophersys/eden:harnesses/versions.env`, read weekly through the
`EDEN_MANIFEST_READ` PAT, and states the contract in its own header: *"eden's
harness-upgrade-check remains the ONE decision point: these rows MIRROR eden's
harnesses/versions.env, they never lead it."* That every pin carries such a row
is itself gated on every pull request by `_ctl/tests/upstream-coverage.test.sh`,
so divergence resolves into the weekly bump by construction. **That is a third,
separate flow — it is not one of the diagram's two breaks**, and adding an
assertion in eden's gate would be a second home for a fact §4.1 exists to prevent.

So: two deferred with triggers, one withdrawn as false. Not three deferrals.

**One toolchain fact that blocks work below.** `sqlc` is **not in any image** —
no pin in `versions.env`, no install in `base/Dockerfile` or
`_delta/components/*.sh` — so `apps/platformgateway/persistence/ctl.sh:29`
`require_cmd sqlc` exits 127 everywhere. It has never been noticed because the
`generate` and `verify` targets (`persistence/project.json:9,13`) are in **no**
gate verb list: the generated-code drift check has never run. `sqlc` is a Phase-0
item because migration `0005` (P2-1) extends the `schema/schema.sql` it
type-checks. `oapi-codegen` is *not*: it serves the 482-line OpenAPI contract
that P1-1 replaces with protobuf. Pinning a binary for a contract Phase 1 deletes
is pure waste.

---

## 5. The libs rework

Audit of all 16 Go modules (each its own `go.mod`, wired by `replace ../<lib>`) and
all 4 TypeScript packages (a Bun workspace, `libs/typescript/package.json`).

**The house shape is `New(configuration Config, dependencies Deps) (*T, error)`** —
a two-argument superset of the stated contract, with both cfg *and* deps validated
at construction. 14 of 16 follow it exactly. That is better than
`New(cfg)` and should be **ratified as the contract**, not migrated away from
(Decision D3, §8).

| lib | what it is | constructor (file:line) | globals / `init()` | Run/Close | verdict | effort |
| --- | --- | --- | --- | --- | --- | --- |
| **agentruntime** | agent process lifecycle + heartbeat | `New(Config, Deps) (*Runtime, error)` `agentruntime.go:111` | dead `var _ = errors.KindInvalid` `:155` | `Run(ctx) (TerminationReason, error)` `runtime.go:26` — 2 returns | REWORK | **S** |
| **agentsession** | harness session pool + adapters | `New(Config, Deps) (*Pool, error)` `pool.go:25` | none mutable | `session.Close(ctx)` `session.go:157` | CONFORMS | — |
| **codeinsight** | repo churn/complexity analysis | `New(Config, Deps) (*Analyzer, error)` `codeinsight.go:166` | none | none (request-scoped) | CONFORMS | — |
| **configuration** | config file parser | `New(Config, Deps) (Parser, error)` `parser.go:37` | **`init()` `testsupport.go:21`** writing **mutable global `var Build`** `internal/docbuild/docbuild.go:31` | none | REWORK | **M** |
| **dependencies** | Clock/Random/Sink ports | no `New`; `Resolve(Set)` `:94`, `Validate(Set)` `:111` | none | none | CONFORMS | — |
| **edenhttp** | HTTP spine, JWT, SSE | `New(Config, Deps) (*Spine, error)` `edenhttp.go:57` | none | `natssse.Bridge.Stream(ctx)` `natssse.go:111` | CONFORMS | — |
| **envelope** | envelope encryption via KEK | `New(Config, Deps) (*Envelope, error)` `envelope.go:119` | none | none | REWORK | **S** — **no `envelopetest` fake** |
| **errors** | typed error kinds | `New(kind, message) *Error` `errors.go:164` | const-like `kindTokens` `:53` | none | CONFORMS | — |
| **forge** | GitHub repo operations port | `githubadapter.New(Config, Deps)` `githubadapter.go:120` | **exported mutable `var ProtectedRepositoryNames`** `guard.go:13` — a delete-denylist any consumer can `delete()` from | none | REWORK | **S** — also **no `forgetest` fake** |
| **gitrepository** | local git operations | `New(Config, Deps) (*Repository, error)` `gitrepository.go:211` | `var idCounter atomic.Int64` `gitrepositorytest/model.go:13` (test pkg, cross-test state) | none | REWORK | **S** |
| **objectstorage** | S3/MinIO client | `New(Config, Deps) (*Client, error)` `objectstorage.go:261`; `minioadapter.New` `:114` | none | none | CONFORMS | — · **UNUSED by every app; adoption DEFERRED past P3** (ledger) |
| **observability** | OTel provider | `New(Config, Deps) (Provider, error)` `observability.go:110` (interface return, deliberate) | none | none | CONFORMS | — |
| **orchestrator** | agent pool reconciliation + postgres | `New(Config, Deps) (*Pool, error)` `pool.go:103`; `postgresstore.New(_ Config, Deps)` `postgresstore.go:50` — **Config ignored** | `//go:embed schemaDDL` `:19` (benign) | **`Start(ctx)` `lifecycle.go:23` + `Close(ctx)` `:77`** — `Start`, not `Run` | REWORK | **S** |
| **secrets** | secret refs, redaction, zeroize | `New(Config, Deps) (*Mediator, error)` `mediator.go:17` | **`init()` `secret.go:62`** writing **mutable global `var hook`** `internal/mint/mint.go:20` | none | REWORK | **M** |
| **testing** | deterministic runner + fakes | `New(Config, Deps) (*Runner, error)` `runner.go:27` | none | provides `AssertLifecycle` `lifecycleconformance.go:46` | REWORK | **S** — `New` **never returns non-nil error**; the `error` is vestigial |
| **workspaceprovider** | docker/k8s workspace provisioning | `New(Config, Deps) (*Provisioner, error)` `substrate.go:91`; `dockeradapter.New(Config)` `:59` | `legalTransitions` map `statemachine.go:26` (unexported) | `Reconcile(ctx, selector)` `supervise.go:223` | CONFORMS | — |
| **@eden/scale** | modular scale generator | `modularScale(seed, from, to)` `src/index.ts:107`, throws `ScaleSeedError` `:68` | none | pure | CONFORMS | — |
| **@eden/theme** | OKLCH token engine + contrast | `generateTheme(seed, options)` `src/generate.ts:330` | none | pure | CONFORMS | — |
| **@eden/primitives** | Svelte 5 accessible components | `derive*Tokens(theme)` e.g. `src/tabs/tokens.ts:84` | none | props | CONFORMS | — |
| **@eden/visualization** | chart widgets | `deriveHotspotMapTokens(theme)` `src/hotspot-map/tokens.ts:111` | none | props | CONFORMS | — |

**Nothing dies.** Every lib is either used by an app or by a sibling lib.
`objectstorage` is unused by apps and **stays unused through P3** — the object
store leg is deferred (ledger). `libs/protocols/`, `libs/python/`, `libs/rust/`,
`libs/zephyr/` are empty directories (`protocols/` holds only `.gitkeep`) —
`protocols/` becomes the proto home (§7 P1).

**Test discipline is already strong and should not be touched**: `-race` on
every lane (`libs/go/_ctl/lib.sh:123` unit, `:215` property with
`RAPID_CHECKS=1000`, `:236` lifecycle, `:263` load), a `<lib>test/` fake package
in 14 of 16, and a shared lifecycle conformance driver
(`testing/lifecycleconformance.go:46`).

**The measured gap against round 1's standard** ("table tests + race detector +
**one fake per external dep**") is exactly two libs: `envelope` and `forge`.
`forgetest` is written in P2-0, because project creation needs it. `envelopetest`
is **not on the first slice's path and is deferred with a trigger** (ledger) —
recorded, not forgotten. Three further REWORK libs — `agentruntime`, `envelope`
and `testing` — are likewise deferred with triggers rather than dropped; an
earlier draft cut the migration table from eight rows to two and lost them
silently, which is the failure mode the ledger exists to prevent.

### 5.1 The libs leg — one item, and it is priced inside Phase 2

Rows carrying zero effort are a reading order, not a plan. But removing the leg
from the plan is not the same as removing it from the arithmetic: an earlier
draft did both, leaving S-sized work that the same document called "a
precondition of the spine" unpriced and unowned. The leg is **one item**, and it
is **P2-0**, budgeted in Phase 2.

| # | Lib | Work | Effort | Owned by |
| --- | --- | --- | --- | --- |
| 1 | **forge** + **gitrepository** | project creation cannot happen without them (`CreateRepository`, seed clone→flatten→push). **forge:** write the missing `forgetest` fake; retire the exported mutable `ProtectedRepositoryNames` (`guard.go:13`). **gitrepository:** retire the cross-test global `var idCounter atomic.Int64` (`gitrepositorytest/model.go:13`) — the defect its REWORK verdict is *for*, and the only one of the eight REWORK libs that had neither an owner nor a trigger. | S each ≈ 1 agent-day | **P2-0** |

**`orchestrator` left this list with the fleet.** It was here as "the only
postgres-backed durable store and the only real lifecycle pair" — but the store
the first slice uses is the sqlc/pgx layer under migration `0005`, and the only
consumer of `orchestrator` was the `launch_supervisor` saga step, which the fleet
deferral takes with it. Deferred with the fleet leg, one trigger, one row.

`errors`, `dependencies`, `observability`, `@eden/theme` and `@eden/primitives`
are on the first slice's path and need **no work** — they already conform. They
are dependencies, not tasks.

**`edenhttp` is not on this list, and that is the design.** The first draft had it
here at effort M — "add the gRPC transport" — which would have mounted
grpc-gateway *beside* an independent JWT/SSE spine: two transports and two auth
surfaces inside the one binary §1.1 exists to unify. The intent's named property
is one protobuf contract serving both gRPC and REST+JSON. So P1-2 is **one
stack**: a grpc-gateway `ServeMux` plus a stdlib mux for `go:embed static/` and
`/healthz`. Auth is oauth2-proxy and the tailnet, per round 5, so edenhttp's JWT
layer is redundant at the edge; and once the live surface is a gRPC server-stream,
the `natssse` bridge has no consumer. `edenhttp` keeps its lib audit row and stays
available — it is simply not part of the first slice.

**`secrets` and `configuration` are NOT off the first slice's path, and an earlier
draft deferred them on a premise its own phase items refute.** P1-2 routes config
and credentials through both; §2.4 routes the database DSN through both; §3.6 and
P1-0 rest the inner loop's whole one-truth claim on "the same variable names
`configuration` parses". The ledger trigger written for them was "either lib is
touched for another reason" — which fires the moment P1-2 exists. Round 1's
contract is "no globals, no `init()`", and §5 measures these two as the only libs
violating it. So they land in **P1-2**, priced at S each rather than M: the fix is
contained — delete the `init()` in `configuration/testsupport.go:21` and pass
`docbuild.Build` through `Config`; same shape for `secrets/secret.go:62` →
`internal/mint.hook`. Leaving the named contract unmet on exactly the path the
first slice runs through is the defect §5 exists to prevent.

---

## 6. Schema v0 — orgs → projects → workflows

### 6.0 What iotea actually holds, and what to take

iotea carries **two incompatible org models**, and the active one has no
organization at all. The rename was started and never finished — three
vocabularies coexist and the UI calls SDK methods that do not exist
(`apps/hub/src/actions/spaces.ts:15` calls `.spaces.create`, which is not among
the SDK's getters at `libs/iotea-js/src/index.ts:106-344`).

| | Legacy — `prisma/iotea.prisma` | Active — `prisma/schema.prisma` |
| --- | --- | --- |
| root | `Organization` `:240` | `User` (`prisma/schema-hierarchy.md:1-28` records the deletion as deliberate) |
| spine | Org → Space `:18` → Channel `:48` | User → Project `:65` → **Application** `:107` → Workflow `:133` |
| used by | the whole `apps/hub` UI, routes `/organizations/[orgId]/spaces/[spaceId]/channels/[channelId]` | the Go API + SDK |
| generated? | no | **yes** — `prisma/project.json:42` |

So **orgs → projects → workflows is iotea's UI shape, and iotea's backend never
landed it.** Copy the shape. Do not copy the execution.

**Take (2):** the org as the tenancy boundary with billing attached to it
(`iotea.prisma:243` `stripeCustomerId` — and nothing else about billing in the
database); and `@@unique([organizationId, userId])` on membership (`:272`).

**Leave (9):** `Application`, the level between project and workflow — pure
indirection, it owns nothing but workflows (`schema.prisma:107`); `Connection`
rows duplicating a graph that already lives in `config Json` (`:157-179`);
`Tag` + `AppliedTag` — eight nullable foreign keys and ten indexes for one
polymorphic pointer, its constraint written as a comment (`:397-398`); `Billing`
as a table with `amount Float?` for money (`:181-199`); `MemberSpacePermission`
until per-project roles actually differ from org roles (`iotea.prisma:284`);
every IoT-domain entity; **the four audit columns `created_at/by` +
`updated_at/by` on every model** — `*_by` is two columns × eight tables recording
an actor that is always the same person or the saga itself, and `created_at` /
`updated_at` are already in the existing DDL without them; **the two-level
authorization split** — round 5 is explicit ("single user now; multi-user RBAC
becomes a schema concern later"), and taking the split while leaving
`MemberSpacePermission` would be taking the cost without the capability; and
**Next.js-style route groups** — a convention for chrome shared across many
pages, and there are three routes.

**Three defects to fix rather than inherit:**

1. **`Space` has no `@@unique([organizationId, name])`** (`iotea.prisma:18-39`) —
   two projects in one org may share a name. §6.1 adds the constraint.
2. **Runs are telemetry with an 8-hour TTL**, not records. No `*Execution` model
   exists in any `.prisma` file; executions live in ClickHouse
   (`deploy/engine/production/values/channel-obsv-otel-collector-config.yaml:39`
   `ttl: 8h`). §6.1 puts `workflow_runs` in Postgres.
3. **Project creation is not transactional.** Two separate `.Exec(dbCtx)` calls,
   no transaction, no compensation: if the permission-set insert fails, the
   project row is already committed and you get an orphan
   (`services/http-api/api/v1/projects/create/execute.go:47-54, 72-79`). eden's
   create-saga is already better — a durable, keyed, resumable step ledger
   (`apps/agentgateway/internal/gateway/saga.go`, steps
   `projectcreate/saga.go:20-23`). Keep eden's.

One convergence worth naming: iotea's handler pipeline
**parse → validate → contextValidate → execute → respond → async action**
(`services/http-api/api/v1/projects/create/handler.go:27-53`) is the same shape
as eden's already-ratified five-files-per-route rule
(`docs/architecture/16-application-template-system.md:116-122`). Two independent
arrivals at one design is the strongest evidence either provides. Keep eden's.

Finally, iotea has **no template or scaffold concept at all** — zero hits for
project templating across its API, UI and SDK. "eden as the template" (F4) is
eden's own idea and has no reference implementation to copy.

### 6.1 The shape

**Eight tables in schema v0, and no ninth.** Five already exist and are already
the IOTEA model, ported and cited as such (`schema.sql:32`, `:82`). Three are new
or generalised. **One migration, `0005`** — Phase 3 adds no table (below).

```
organizations ──┬── organization_members ──── users ──── accounts
                │        └── permission_sets
                │
                └── projects ─── workflow_runs ─── workflow_steps

   `audit_events` exists today (`auditpersistence/postgres.go:59-67`) and is
   untouched. v0 builds no `events` table — see below.
```

| Table | State today | Action |
| --- | --- | --- |
| `users` | exists — `schema.sql:10` | keep |
| `organizations` | exists — `schema.sql:40` | **add `slug`** (URL identity, §1.2) |
| `permission_sets` | exists — `schema.sql:50` | keep on disk; **not read on the project path** |
| `organization_members` | exists — `schema.sql:64` | keep |
| `accounts` | exists — `schema.sql:92` (mirrors the IOTEA prisma `Account`, `:82`) | keep |
| `connectors`, `connector_secrets` | exist — `schema.sql:122`, `:146` | keep, out of slice |
| **`projects`** | a JSONB blob in the other service — `projectpersistence/postgres.go:90-93` | **rewrite as a real table under an org** |
| **`workflow_runs`** | does not exist | new — carries `kind` directly |
| **`workflow_steps`** | exists as `project_create_steps` — `createsteppersistence/postgres.go:86-95` | **generalise** — the create-saga ledger IS this table |
| ~~`workflows`~~ | — | **not built.** See below. |
| `audit_events` | exists — `auditpersistence/postgres.go:59-67` | **untouched.** v0 builds no `events` table; `workflow_steps` already stores the only transitions v0 produces (below). |

**Why there is no `workflows` table.** v0 has exactly one kind
(`create-project`), so every row would be derivable from its runs and would carry
no state of its own. The ORGS → PROJECTS → WORKFLOWS hierarchy survives where
Mateo named it — as an addressable URL level and a run grouping, both driven by
`workflow_runs.kind`. The table is one migration away the day a second kind or a
per-workflow setting exists.

**Why there is no `events` table at all** — neither in `0005` nor later — is
argued below, after the migration.

```sql
-- 0005_org_project_run.sql
--   organizations: 1 ALTER ADD · 2 UPDATE backfills · 1 ALTER SET NOT NULL · 1 INDEX
--   3 CREATE TABLE. No seed statement: the default organization is planted by
--   edend at startup (P2-1), extending the seed the code already carries
--   (schema.sql:32-48).
-- Nullable first, backfill, THEN constrain: a bare `ADD COLUMN slug text NOT NULL`
-- cannot apply to a non-empty organizations table.
ALTER TABLE organizations ADD COLUMN slug text;
UPDATE organizations SET slug = 'gophersys' WHERE slug IS NULL AND is_default;
UPDATE organizations SET slug = 'org-' || left(id::text, 8) WHERE slug IS NULL;
ALTER TABLE organizations ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX organizations_slug ON organizations (slug);

CREATE TABLE projects (
    id              uuid        PRIMARY KEY,
    organization_id uuid        NOT NULL REFERENCES organizations (id),
    slug            text        NOT NULL,
    name            text        NOT NULL,
    status          text        NOT NULL,          -- closed set, gateway/project.go:56-64
    repository_url  text        NOT NULL DEFAULT '',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, slug)   -- the constraint iotea's Space lacks
);

CREATE TABLE workflow_runs (
    id          uuid        PRIMARY KEY,
    project_id  uuid        NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    kind        text        NOT NULL,              -- closed set; v0: 'create-project'
    status      text        NOT NULL,              -- pending|running|succeeded|failed|cancelled
    started_at  timestamptz,
    finished_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- the create-saga ledger, generalised. The PRIMARY KEY *is* the idempotency key.
CREATE TABLE workflow_steps (
    run_id      uuid        NOT NULL REFERENCES workflow_runs (id) ON DELETE CASCADE,
    step        text        NOT NULL,
    status      text        NOT NULL,              -- pending|done|failed
    output      jsonb,
    started_at  timestamptz NOT NULL,
    finished_at timestamptz,
    PRIMARY KEY (run_id, step)
);
```

**Six** columns earlier drafts carried and this one does not, each failing the
same test — a stored copy of something the row or the code already owns, or a
column with no v0 producer and no v0 reader:

| Dropped | Owned instead by / why |
| --- | --- |
| `workflow_steps.ordinal` | the fixed ordered slice at `projectcreate/saga.go:20-23`. The resume rule is "first not done" over that slice, and the exit proof reads `select step,status` — never `ordinal`. A stored ordinal is the "two hand-kept descriptions of one system" defect (§0.1) at column scale. |
| `workflow_steps.idempotency_key` | `PRIMARY KEY (run_id, step)`. It is fully determined by the key. A stored derivation can disagree with its source; a random one would itself have to be persisted before use to survive the crash it exists to survive. |
| `projects.template_ref` | the configuration value at `projectcreate.go:76-82` (F4). In v0 every row would hold the same string and no exit criterion reads it. |
| `projects.default_branch` | identical to `template_ref`'s case: it holds `main` for every row and no exit-proof line reads it. |
| `projects.idea` | **no producer at all in v0.** The create path is `CreateProject {org, name}`; the consumer of an idea is the deferred supervisor; the two v0 steps are `provision_repo` → `seed_template`. |
| `events.actor` | the same test that deleted 16 `*_by` audit columns for recording "an actor that is always the same person or the saga itself". `events`' only v0 producer is the create-project run's own step transitions — always the saga. Its defence named provenance "where it matters", and that place is itself a ledger row (GitHub/CI ingestion), so the column and its reason share one trigger. |

Migration `0005` is **22 columns** across three CREATEs, down from 41.

**The v0 create-project run is TWO steps, not four.** The saga as it exists today
has four (`projectcreate/saga.go:20-23`): `provision_repo`, `seed_template`,
`launch_supervisor`, `supervisor_ready`. The last two spawn and await an agent
supervisor — that is fleet work, and the fleet leg is deferred as one piece
(§1.1). Keeping them while deferring NATS and `eden-agent` was the pass-1 defect:
Phase 2 would have asserted a supervisor reaching ready over a transport no phase
brings up.

So v0 runs `provision_repo` → `seed_template`, and the terminal project status is
**`seeded`** — a provisioned, seeded repository, which is exactly what round 6
asks for ("a new project is scaffolded based on how eden works"). Both steps
become `workflow_steps` rows of one `create-project` run; the driver keeps its
resume-from-first-not-done logic unchanged, and the two deferred steps append to
the same ordered slice when the fleet lands. `ProjectStatusLaunchingSupervisor`
and `ProjectStatusSupervisorReady` stay in the closed status set
(`gateway/project.go:56-64`) — unreachable in v0, not deleted.

**Phase 3 adds NO table.** An earlier draft created `events` (a `bigserial`
stream) in a migration `0006`, wrote a row on every create-project step
transition, and served it as a third RPC. All of it is cut, because v0 has
exactly one event producer and `workflow_steps` already stores what it produces:

| The event row would have held | Already stored, since P2-1 |
| --- | --- |
| that a step began | `workflow_steps.started_at` |
| that a step finished, and how | `workflow_steps.status` + `finished_at` |
| which run it belonged to | `PRIMARY KEY (run_id, step)` |
| ordering | the fixed slice at `projectcreate/saga.go:20-23` |

That is a second hand-kept description of one fact — §0.1's named iotea defect,
and the same test that removed `ordinal`, `idempotency_key`, `template_ref` and
sixteen `*_by` columns from this very section.

**The stream bought nothing over polling either.** Its own design polled: a 1 s
tick over an index, pushed to a client that was already calling
`GetProjectSurface` on navigation. Client polling with a stream in the middle
costs a resumability contract (`from_seq`), an ordering authority, and a
reconnect story — to make a board row change inside two seconds, which the SPA
re-calling one unary RPC does by construction.

**Round 5's "live fleet/CI events" names two producers, and both are deferred.**
The fleet plane is one ledger leg; GitHub/CI ingestion is another. v0 ingests
neither, so there is no third-party event to stream. `audit_events` stays exactly
where it is today (`auditpersistence/postgres.go:59-67`) — untouched, not
generalised.

The whole leg reopens on **one** trigger, which replaces five separate ledger
rows: *the first event producer the product does not itself perform.*

**Tempted, not taken:** `project_members`, soft-delete columns, a `workflows`
table, `workflow_definitions`, a `runs.trigger` provenance column, per-project
settings, and per-project permission grants. Each is one migration away when a
second user, a second org or a second workflow kind exists.

### 6.2 Migration tooling — **goose, as a library**

Recommend `github.com/pressly/goose/v3` used as a Go library, applied by a
Kubernetes Job before the rollout, never by hand — round 3: *"migrations =
versioned SQL in-repo … applied by a job, **never by hand**"*.

**The Job is a chart object (P1-3), and it does not violate the one-workload
rule.** `edend migrate` is an argv subcommand of the same binary and the same
image; it runs to completion under a `helm.sh/hook: pre-install,pre-upgrade` and
exits. What §1.1 rejects is a second **long-running role** — a second Deployment,
a second values block, a second rollout story. A hook Job is none of those. The
distinction is worth stating because an earlier draft asserted "applied by *the*
Job" with a definite article while no item built one, and the P2 proof
(`select status from projects…`) would have been satisfied identically by today's
in-binary migrator — an unfalsifiable mechanism change, which is the FAIL-NOT-SKIP
failure this document is built against.

Two sentences: the repository already writes goose-format SQL and applies it from
the binary through a hand-rolled 20-line directive reader
(`apps/platformgateway/persistence/migrate.go:68-72`, migrations `0001`–`0004`),
so adopting the real library **deletes** code rather than adding a tool. Atlas
would need a new pinned binary in an image that today pins no migration tool at
all (`.devcontainer/versions.env` — no `ATLAS`, no `GOOSE`, no `SQLC` row) and a
second declarative source of truth beside the `schema/schema.sql` that sqlc
already type-checks against.

---

## 7. The phased plan

Effort is **agent-days**: one agent, one day, inside the devcontainer.

### Phase 0 — make the gates real (2.5 agent-days)

Nothing below can be trusted until a red gate is possible.

| # | Item | Evidence of the defect |
| --- | --- | --- |
| P0-1 | Bump the three submodule pointers to `origin/main`. **Once** — `git submodule update --remote`, judged by the gates that already exist. eden pins `infrastructure` **244 commits** behind (pin `8cb1543`, 2026-08-10) and `libs` **214 commits** behind (pin `50940e1`, 2026-08-11); `.devcontainer` is pinned **300 commits** behind. | `git ls-tree HEAD` vs each submodule's `origin/main` |
| P0-2 | Make a missing `nx` a **failure**: 10 verbs + `validate` in `eden/.ci/ctl.sh` (`:93,101,109,117,124,129,134,145,159,173`; `validate` at `:86-88`). Delete the dead `-z` arm at `:45`. | §4.2 |
| P0-3 | Make an empty gateable set a **failure** in `libs/.ci/ctl.sh:120-123`. | §4.2 |
| P0-4 | Pin `sqlc` in `.devcontainer/versions.env` + install it, and wire `persistence verify` into a gate verb list. Today the drift check exits 127 and is in no lane. **Not `oapi-codegen`** — §4.3. | `persistence/ctl.sh:29`; `persistence/project.json:9,13`; no pin in `versions.env` |
| P0-5 | Add `timeout-minutes` to all 10 eden jobs (currently **zero**), and move `harness-upgrade-check.yml:20` off `ubuntu-latest`. | measured: `grep -c timeout-minutes .github/workflows/*.yml` → 0 for all 5 |
| **P0-6** | **Write the ctl.sh standard down and give it one home.** `.devcontainer/docs/ctl-standard.md` = C1–C10 (safety) + I1–I7 (structure) + **V1–V5, the common verb vocabulary** (§4.2), and `_ctl/lib.sh` becomes the shared library **all three submodules source** — `eden`, `libs` **and `infrastructure`**. `ctl.sh verbs --check` walks all **56 `project.json`** and asserts the per-class expectation — not five targets everywhere, which would manufacture ~200 no-op greens (§4.2). Round 2 is almost entirely this: "**Common verbs**, simple clean style, TRUE abstraction layers", applied "globally to all submodules". | §4.1, §4.2 |
| **P0-7** | **Enable terraform state locking** in `infrastructure`'s OCI backend and fix the README that claims it is already on. | `providers/state-backend/backend.hcl:29-36` (locking **disabled**) vs `providers/state-backend/README.md:16-18` (claims enabled) |

**P0-7 is a correctness item, not a documentation fix.** Round 1, production:
"Terraform state in the Oracle bucket; **concurrent workflows/agents on the repo
must not conflict (state locking)**." The whole design assumes parallel agents. An
earlier draft filed this inside a parenthetical on an object-store decision, where
it would have been delivered only if someone happened to read a footnote.

**cictl P0 (#92) is NOT in this phase.** It is a different, already-running
program: the intent records "#92: APPROVED as recommended … Build launched
2026-08-25", sized at ~10 h under **ledger #44**, not #130. Counting it here
double-books the effort and makes Phase 1 wait on unrelated work. It also fails
this phase's own test — an AI review is advisory, not a pass/fail correctness
gate, and no exit proof in P1–P3 consumes it. And it carries an unresolved
blocker that belongs to #44: `cictl`, `hnslint` and `review` are PUBLIC, and
`arc-review` refuses a public repository, which is an open runner-group decision.
Phase 0 must not inherit a gate that cannot go green.

**Exit proof — every line must be executed and shown:**

```
git -C eden submodule status                 # 3 pointers == origin/main
mv $(which nx) /tmp/ && bash .ci/ctl.sh affected-check ; echo $?   # → 127, not 0
NX_BASE= bash .ci/ctl.sh affected-check                            # empty base resolves;
                                                                   # the dead -z arm is gone  [P0-2b]
bash libs/.ci/ctl.sh affected-gate-fast  (PR touching only .ci/)   # → non-zero
bash apps/platformgateway/persistence/ctl.sh verify                # → 0, ran sqlc
bash .ci/ctl.sh affected-gate-fast 2>&1 | grep -c 'persistence:verify'
                                                                   # → 1: the drift check is IN
                                                                   #   a lane, which is the half
                                                                   #   of P0-4 that matters  [P0-4b]
grep -c timeout-minutes .github/workflows/on-pr.yml                # → 2
grep -rn 'ubuntu-latest' .github/workflows/                        # → no matches   [P0-5b]
# P0-6, proven by sourcing and by dispatch, not by existence:
grep -c . .devcontainer/docs/ctl-standard.md                       # the standard exists
bash -c 'source .devcontainer/_ctl/lib.sh && require_cmd definitely-not-a-tool' ; echo $?
                                                                   # → 127 from the SHARED lib
grep -L '_ctl/lib.sh' eden/.ci/ctl.sh libs/.ci/ctl.sh infrastructure/ctl.sh
                                                                   # → empty: ALL THREE source it
bash .ci/ctl.sh verbs --check                                      # walks ALL 56 project.json
                                                                   # → 56 checked, 0 off-class,
                                                                   #   0 undeclarable declared
# and the negative, which is the point of the class table:
add a no-op `typecheck` to a Go module ; bash .ci/ctl.sh verbs --check
                                                                   # → non-zero: a target it
                                                                   #   cannot really run
# P0-7, proven by contention not by config:
terraform plan &  terraform plan          # second run BLOCKS on the lock, then proceeds
```

Every item above has a line. An item with no proof line passes its gate by
silence, which is the FAIL-NOT-SKIP failure this document is built against — and
an earlier draft shipped three such items (P0-5's second half, P0-6, P1-8).

### Phase 1 — env machinery + walking skeleton (8.25 agent-days)

| # | Item |
| --- | --- |
| **P1-0** | **The inner loop — `ctl.sh dev`.** `edend` runs on the HOST (inside the devcontainer) against the k3d substrate's Postgres, MinIO and OTLP through port-forwards; Go rebuilds with `go run`, Svelte serves through `vite dev` with HMR. **No image build, no `helm upgrade`, no deploy.** Its environment is PROJECTED FROM the same `values-dev.yaml` the chart renders, through the same variable names `configuration` parses (§5) — one source of configuration, two runtimes. Round 2 names this "the current big problem". |
| P1-1 | `libs/protocols/eden/v1/*.proto` — `Organization`, `Project`, `Run`, `WorkflowKind` (the closed enum), and the **two** v0 RPC definitions — `GetProjectSurface` and `CreateProject` (§1.2). **`buf generate` emits BOTH clients**: Go into `libs/protocols/gen/go`, TypeScript into a new `libs/typescript/client` workspace package. Round 5: "typed clients generated for Go **and TypeScript**". Without the TS half the SPA hand-writes the types and protobuf buys nothing — and the generated enum is what makes a `ListWorkflows` RPC unnecessary. `buf` is already pinned (`.devcontainer/versions.env:186`). |
| P1-2 | `edend` — one binary, one role, ONE stack: grpc-gateway `ServeMux` + a stdlib mux for `go:embed static/` and `/healthz`. **No RPC is implemented in this phase**; the service is registered and reflection lists it. No second spine, no in-binary JWT (§5.1) — oauth2-proxy stands in front. Config arrives through `configuration`; the database DSN comes from CNPG's own `<cluster>-app` Secret, not from Vault (§2.4). **Includes the two `init()`-writes-a-global fixes** (`configuration`, `secrets`) — this is the path that touches them (§5.1). |
| P1-3 | `deploy/chart` **written by hand**, ONE long-running workload (`edend`). Objects: `Chart.yaml` with the §2.2 annotation pair · Deployment · Service · Ingress · **CNPG `Cluster`** (the per-environment database the operator reconciles, carrying the three `postgres.backups.*` knobs) · **migration `Job`** with a `helm.sh/hook: pre-install,pre-upgrade` · **`ExternalSecret`** (the `secrets` member's only consumer — it materialises the barman `s3Credentials` the CNPG `Cluster` needs, and **nothing else**: the database DSN comes from CNPG's own `<cluster>-app` Secret, §2.4. In dev its payload is empty, because dev backups are off) · three values files. `deploy/servicespec` and the compose renderer stop being used; **the D4 sweep removes both after this phase's exit proof passes**, never in the same change. |
| P1-4 | `ctl.sh env up\|stop\|start\|down\|ls\|preflight` + the dev and staging values profiles. **Reaping has no CronJob** (§3.3): a reap step at the top of `env up`, plus a scheduled CI lane against the staging host cluster. Prod stays Argo's (§3.1). |
| P1-5 | The k3d capability bring-up lands in **`infrastructure`**: the **six service capabilities** as pinned upstream charts — CNPG (operator), ingress-nginx + cert-manager, the secrets provider, an OTLP collector, oauth2-proxy, **and MinIO** (the `objectstore` member, §2.2). The seventh annotated member, `substrate`, is k3d-native and is asserted, not installed. `env up --profile dev` calls it; §2.3's probe *is* it. |
| P1-6 | L1/L2: **two new contracts** — `contracts/substrate.md` (storage · namespaces+quota · RBAC shape · nodes · autoscaling) and `contracts/objectstore.md` (an S3 endpoint that accepts a write); the `capability:` datum in `contracts/README.md`; the two chart annotation fields (**7 annotated**, **8 members**); `verify-capability` (hermetic: every `fulfilled_by:` path resolves); `env preflight` (live probe, **10 assertions** — §2.3). |
| P1-7 | **Test suites for the new bash, each in the repository that owns the verbs**: `eden/.ci/tests/env.test.sh` and `infrastructure/tests/capability.test.sh`, both SOURCING the shared harness library from the `.devcontainer` submodule. A suite living *in* `.devcontainer` would invert the dependency the whole §4 layer rests on — `.devcontainer` is a submodule OF its consumers, so it cannot exercise `eden ctl.sh env up` without checking out its own consumer, and §4.2's precondition points the other way ("the shared library must never require the monorepo"). It would also make every `env` verb change need a pull request in a second repository plus the manual pointer bump §4.3 diagrams as the chain's one break (S1, deferred) — so a test would lag its verb by exactly the gap the plan declines to close. C10 already gives the split: shared BODIES in the library, per-unit data and dispatch in the unit; **tests are per-unit data**. Round 2 asks for bash "tested, catching everything", and §4.1 measures that the reference implementation has **zero** bash tests, so there is nothing to inherit and every reason not to repeat it. `infrastructure` is included because the L1/L2 contract — this blueprint's own invention — rests entirely on those scripts being trustworthy; an earlier draft funded a suite for the largest new surface and left the second-largest with neither library nor tests. |
| P1-8 | **Connect eden's `.claude/` to the submodule — do not copy into it.** `eden/.claude/settings.json` resolves the devcontainer's shared rules, and `eden/CLAUDE.md` cites the three homes P0-6 established (`ctl-standard.md`, `versions.env`, `images.yaml`). Still **no `.claude/rules/` tree in eden**, because `eden/CLAUDE.md:11-12` forbids re-*defining* a concept — but it does not forbid *connecting* to one, and round 1 asked for a connection. `.claude/agents/` and `.claude/skills/` are not enumerated in this phase and carry a ledger row. |
| **P1-9** | **The PR/CI caller.** One hand-written `.github/workflows/pr-env.yml` — one file, one repository, one caller, no generator: `env up --profile staging --id pr<N> --ttl 48h` on open/synchronize, `env down --id pr<N>` on close. **`staging`, not `dev`, and the reason is stated rather than assumed:** round 1 lists "the PR CI environment" as a *user of the dev workflow*, and a CI runner is not a laptop — it cannot reach a k3d cluster on someone's machine. A PR environment needs a cluster CI can address, real TLS and a real hostname, which is what `staging` means here. The cost round 1 warns about is bounded by the 48 h TTL and by the reap step; and a PR env that could not be backed up would not be pre-production, which is the profile's whole point. Round 1 names dev's second user as "the PR CI environment"; round 3 says "ONE code path for humans, agents, CI. **Nothing implicit; PRs call it explicitly.**" §3.2 builds the whole minting rule around "the PR number in CI" and uses `pr142` as its worked example — and of the three callers the single code path exists to unify, this was the only one nothing invoked. |

**P1-8 is a correction, not a restatement.** An earlier draft delivered round 1's
"eden's `.claude/` must be **1:1 connected** and leverage the `.devcontainer`
submodule" as three citation lines plus a refusal, and cited the one-home rule as
the justification. That rule forbids defining a concept twice; it says nothing
against wiring. Three citations out of a `.claude/` tree is a scope reduction, and
it was made inside a phase-item cell rather than surfaced. The connection is the
deliverable; what remains unenumerated is now visible in the ledger instead of
being silently absent.

**Exit proof:**

```
bash ctl.sh env up --profile dev --id mateo       # k3d + substrate + chart, from zero
kubectl -n eden-mateo get cluster.postgresql.cnpg.io,job,externalsecret
                                                  # all three non-obvious chart objects [P1-3]
kubectl -n eden-mateo get secret eden-db-app -o jsonpath='{.data.uri}' | head -c1
                                                  # CNPG's own Secret is what edend reads
kubectl -n eden-mateo get externalsecret -o jsonpath='{..status.conditions[0].type}'
                                                  # Ready — and in DEV it syncs an EMPTY
                                                  # payload, because dev backups are off
# the INNER loop, proven by the clock, not by a claim:                                 [P1-0]
bash ctl.sh dev &                                 # host edend + vite, port-forwarded
touch apps/…/handler.go   ; time-to-served < 5 s
touch apps/frontend/…/+page.svelte ; time-to-served < 1 s
diff <(ctl.sh dev --print-env) <(helm template … -f values-dev.yaml | yq '…env')
                                                  # → identical: ONE configuration source
bash ctl.sh env up --profile dev --id agent7      # a SECOND dev env, same cluster
bash ctl.sh env ls                                # both listed, distinct namespaces
curl -fsS https://mateo.dev.eden.<domain>/healthz # 200, TLS from the substrate's issuer
curl -sI  https://mateo.dev.eden.<domain>/v1/     # 302 to oauth2-proxy — auth in front IN DEV
grpcurl -plaintext localhost:9090 list            # the eden.v1 service is listed
grpcurl -plaintext localhost:9090 eden.v1.Projects/GetProjectSurface
                                                  # → Unimplemented. The TRANSPORT is proven;
                                                  #   no product schema is touched.       [P1-2]
curl -o /dev/null -w '%{http_code}' .../v1/projects/x  # → 501, the gateway translates it
bash eden/.ci/tests/env.test.sh                   # sources the submodule's harness  [P1-7]
bash infrastructure/tests/capability.test.sh      # same harness, its own repo       [P1-7]
bash ctl.sh env up --profile staging --ttl 10m --id smoke
bash ctl.sh env up --profile staging --id smoke   # AGAIN → converges, ONE namespace
bash ctl.sh env stop  --id smoke ; bash ctl.sh env ls   # state=stopped, 0 replicas, PVC intact
bash ctl.sh env start --id smoke                  # back to running, same data
bash ctl.sh env down --expired  (after 10m)       # namespace gone; log line names id + age
bash infrastructure/ctl.sh verify-capability      # → 0 (hermetic, no cluster)
gh pr create --draft …                            # a PR on eden
gh run watch                                      # pr-env.yml runs `env up --id pr<N>`
bash ctl.sh env ls                                # pr<N> listed, ttl 48h            [P1-9]
gh pr close <N> ; bash ctl.sh env ls              # pr<N> gone — the CI caller, end to end
node -e 'const {WorkflowKind}=require("@eden/client");console.log(Object.keys(WorkflowKind))'
                                                  # the generated TS enum, client-side   [P1-1]
grep -c 'ctl-standard.md' eden/CLAUDE.md          # → 1, the citation exists             [P1-8]
test -f eden/.claude/settings.json && grep -c devcontainer eden/.claude/settings.json
                                                  # → the connection, not a copy         [P1-8]
# break-tests, run and shown:
#   set chart annotation to >=9.0.0        → `env preflight` exits non-zero, names the version
#   uninstall CNPG from the k3d cluster    → `env preflight` exits non-zero, names databases
#   add `messaging` to the annotation      → `env preflight` exits non-zero, names messaging
#   delete the default StorageClass        → `env preflight` exits non-zero, names substrate
#                                            (WITHOUT it, `helm --wait` hangs on a Pending PVC)
#   delete the MinIO bucket                 → `env preflight` exits non-zero, names objectstore
#                                            (WITHOUT it, staging's CNPG backup has no target)
#   point contracts/databases.md fulfilled_by: at a missing dir → verify-capability non-zero
```

This phase needs **no product schema at all**, and the third line proves it
rather than asserting it: the surface RPC answers `Unimplemented`, which only a
wired transport can do. An earlier draft had P1-2 deliver `GetProjectSurface`
"over an empty database" — but §1.2 defines that RPC as reading `projects`,
`workflow_runs` and `organizations.slug`, none of which exist until migration
`0005` in **Phase 2**. There is no empty database to read: the relations are
absent and the call errors. That was a genuine phase-ordering deadlock, of the
class this document twice claims to have driven to zero — a seam left when
`events` was moved to Phase 3 and P1-2's payload was not re-read.

It also proves the substrate a developer actually gets: storage that binds, TLS,
oauth2-proxy in front **in dev as well**, two parallel agent environments, and a
cluster the probe has asked rather than assumed.

### Phase 2 — create a project, with eden as the template (6.75 agent-days)

The first functionality. The board is not in this phase.

| # | Item |
| --- | --- |
| **P2-0** | **The libs leg** (§5.1): `forge` + `gitrepository` — the `forgetest` fake, and retire the exported mutable `ProtectedRepositoryNames`. ≈1 agent-day. Project creation cannot start without it, so it is priced here rather than floating. |
| P2-1 | **Adopt `github.com/pressly/goose/v3` as a library** (§6.2) — delete the hand-rolled directive reader at `persistence/migrate.go:68-72` — then migration `0005` (§6.1) applied by **the chart's migration Job** (P1-3) — 1 ALTER, 3 CREATEs, 1 backfill. `projects` moves out of JSONB. **Plus the org seed**: `edend` plants the default organization (`gophersys`) and the default user at startup if absent, extending the IOTEA-style seed the code already carries (`schema.sql:6`, `:32-48`). Nothing else in v0 creates an org — two RPCs, neither of them `CreateOrganization` — so without this the P2 proof cannot run on a fresh environment. |
| P2-2 | The create-saga re-homed onto `workflow_runs` + `workflow_steps`, **two steps** — `provision_repo` → `seed_template`, terminal status `seeded`. Logic unchanged. |
| P2-3 | **`TemplateRepositoryURL` → `https://github.com/gophersys/eden.git`**, and the seeder's flatten step gains an exclusion list (`.git`, `poc/`, `docs/attic/`, `.eden-runtime/`, the submodule working trees). That is the whole item. |
| P2-4 | `CreateProject` **and `GetProjectSurface`** (its schema exists from P2-1), the org/project/workflow routes, and the project shell with its **one outlet**. `/w/<kind>` addresses the workflow level; runs group by `workflow_runs.kind`. No rail, no switcher — both are layout, and layout is the P3-1 co-design's (§1.2). |
| P2-5 | **eden onto itself** — eden is created as the first project inside the running product, at the default organization. |

**P2-3 is a configuration change, not a repository.** Round 6 says "Eden itself
is the template", and F4 measured that the template is only a value the saga
reads (`projectcreate.go:76-82`). An earlier draft built a separate
`gophersys/template` carrying eden's shape — which is a second, hand-kept copy of
eden, drifting from the first eden commit after it lands: iotea's deepest defect
(§0.1) rebuilt one layer up, with nothing in the plan asserting the two agree. It
also added a whole repository — a governance type declaration, CI, submodule
pointers, a devcontainer, a bump lane — to a plan whose headline is one image,
one chart, one role. `gophersys/eden` already **is** the shape; pointing at it is
the smaller and the truer move.

**Exit proof:**

```
# P2-0, proven before anything uses it:
go test ./libs/go/forge/...                       # forgetest fake drives the conformance suite
grep -rn 'ProtectedRepositoryNames' libs/go/forge # → unexported, or no match         [P2-0]
grep -rn 'var idCounter' libs/go/gitrepository    # → no match                        [P2-0]
go test -count=5 -race ./libs/go/gitrepository/... # repeated runs, no cross-test state
grpcurl … eden.v1.Projects/CreateProject  {org:"gophersys", name:"probe"}
gh repo view gophersys/probe                      # exists, seeded, non-empty
git clone gophersys/probe && ls                   # eden's shape: ctl.sh, .ci/, deploy/, nx.json
test ! -d probe/poc && test ! -d probe/docs/attic # the flatten exclusions applied
psql -c "select status from projects where slug='probe'"     # seeded
psql -c "select step,status from workflow_steps …"           # 2 rows, both done
# resumability, proven not asserted:
kill -9 <edend> after step 1 ; restart ; the run completes with 2 done rows,
  and step 1's finished_at is unchanged (idempotent replay, not a re-run)
# eden onto itself:
psql -c "select slug from organizations"          # → gophersys, planted by the seed  [P2-1]
psql -c "select slug,repository_url from projects where slug='eden'"
grpcurl … eden.v1.Projects/GetProjectSurface {org:"gophersys", project:"eden"}
                                                  # → {project, runs[]} — now that 0005 exists
open https://mateo.dev.eden.<domain>/o/gophersys/p/eden   # the shell renders, DEV host
open https://mateo.dev.eden.<domain>/o/gophersys/p/eden/w/create-project
                                                  # the workflow level is addressable, no rail
```

The last line uses the **dev** host on purpose. An earlier draft proved Phase 2
on `eden.<domain>` — the prod hostname, reachable only through the Argo promotion
path that Phase 3 builds. That was the phase-ordering deadlock this plan claims
to have removed, hiding in an exit proof.

### Phase 3 — the board as a view inside a project (1.75 agent-days)

The live status board is one surface in the slot, not a separate product.

| # | Item |
| --- | --- |
| P3-1 | The board **designed under the ui research framework and co-designed with Mateo**: census → Gate 1 → layers → Gate 2 → contract → Gate 3 (§1.2), reading `GetProjectSurface` on navigation and re-polling it while a run is live. No stream, no `events` table, no third RPC (§1.2, §6.1). The org/project switcher lands with it (§1.2). |
| P3-2 | Promote dev → staging (`<env-id>`). Prod promotion stays the existing `release.yml` → Argo pull request, **extended to pin the chart revision and `values-prod.yaml` alongside the image digests**, and to **assert** — not merely record — `promoted-from: <env-id>`: the script reads the digests actually running in `eden-<env-id>` and REFUSES to open the PR if they differ from the digests being promoted. |

**P3-2 is not a rebuild, but it is not a no-op either.** Reusing the digest-pin
PR was right; leaving it unchanged was not. Two facts combine badly: that PR
pins image digests built from `main`, and D4 moves the prod manifests into
eden's own chart under an Argo Application with `selfHeal: true, prune: true`.
Without pinning the chart's git SHA in `source.targetRevision`, a chart or values
change in the eden repository reaches the single production cluster **without
passing the gate at all** — and the approval would gate digests while binding to
no inspected staging instance. Pinning the revision and stamping the env-id
closes both.

**Exit proof:**

```
# non-vacuous liveness: cause a real transition, do not simulate one
grpcurl … CreateProject {name:"liveprobe"}
  → the board row changes within 2 s, no page reload — the SPA re-polls
    GetProjectSurface while the run is live, and the change it renders is
    workflow_steps.status moving, not an injected row
# and the negative, so the poll is not vacuous:
kill the poll ; cause a transition → the row does NOT move
# the UI gates, run not asserted (§1.2):
test -f design/board/census.md                  # Gate 1 passed BEFORE any layout word
squint · greyscale · worst-case-string · point · glance   # Gate 2, five drills, shown
Gate 3 drills executed against the live surface
bash ctl.sh env up --profile staging --id releasecandidate
# the prod gate, shown not claimed:
#   run release.yml → show the promotion PR into gophersys/infrastructure:
#   unmerged, waiting on a human, pinning BOTH the image digests AND the chart SHA,
#   with `promoted-from: releasecandidate` in the body
# the binding, proven by refusal: redeploy releasecandidate at a different digest,
#   re-run the promotion → it EXITS NON-ZERO naming both digests. A recorded
#   string nothing compares is the `cost class` defect on the one gate round 1
#   makes non-negotiable.
# the bypass, proven closed: push a values-prod.yaml change to eden main →
#   Argo does NOT pick it up until a promotion PR moves targetRevision
```

**Total: 19.25 agent-days** to a proven dev→staging→prod spine carrying real
project creation and one live board.

**The trajectory is the finding.** Pass 1 cut 33 items to 14.25 days. Pass 2
found that ten of those cuts had removed *requirements* rather than *work* — a
dev environment that could not boot, a saga step set that needed a deferred
transport, an auth model delivered by neither half, a staging without the backups
and observability round 1 names, state locking round 1 names, a TypeScript client
round 5 names — and restoring them cost 4.25 days. Pass 3 then removed 1 day of
complexity the earlier passes had *created*: a template repository, a code
generator with one consumer, an RPC returning a compile-time constant, and a
leader election nothing built.

**The trajectory — the ONE home for agent-day arithmetic in this document.**

| Phase | draft | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | **P10** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 3 | 1.25 | 2 | 2 | 2.25 | 2.25 | 2.5 | 3.25 | 2.5 | 2.5 | **2.5** |
| P1 | 8 | 2.5 | 5.75 | 6 | 6 | 7.25 | 7.75 | 8 | 8.5 | 8.5 | **8.25** |
| P2 | 10 | 8.5 | 7.75 | 6.5 | 6.5 | 6.5 | 6.75 | 6.75 | 6.75 | 6.75 | **6.75** |
| P3 | 5 | 2 | 3 | 3 | 3 | 3 | 3 | 3.25 | 3.25 | 1.75 | **1.75** |
| | **26** | 14.25 | 18.5 | 17.5 | 17.75 | 19 | 20 | 21.25 | 21 | 19.5 | **19.25** |

Pass 10's only movement is **P1 −0.25**: the autoscaling probe's
declared-and-matches-reality half was cut, because comparing a declared posture
requires the per-cluster declaration §2.2 deletes.

**No other table in this document carries agent-days.** Passes 1–7 each kept
their own; four homes for one number generated most of passes 4–8's findings, and
both halves of that generator — the per-pass tables and the per-pass narratives —
are now deleted.



---

## 8. The decisions Mateo owes

| # | Decision | Options (recommendation first) |
| --- | --- | --- |
| **D1** | **The environment domain**, and what stands in front of it. | **(A) tailnet by default — `<env-id>.eden.tail5435d5.ts.net`, TS-issued certs, oauth2-proxy in front; the public zone `<env-id>.eden.mateosegura.com` as an explicit per-env opt-in** (the zone is already Cloudflare-authoritative and homelab already issues LE certs via cert-manager DNS-01, `platform/core/edge/tls/cert-manager/cluster-issuer.yaml:12-25`, so opting in needs no new provider) · (B) public for every env · (C) tailnet only, never public. **Recommend A.** Round 5 names the model as "tailnet **+** oauth2-proxy" — two layers, not a choice between them. An earlier draft recommended the public zone for every ephemeral env *and* removed the in-binary JWT on the grounds that oauth2-proxy would cover it, while scheduling oauth2-proxy nowhere: that combination would have published an unauthenticated surface per staging instance. The `identity` capability (§3.5) is the fix — oauth2-proxy in front in **all three** profiles, no per-profile knob; this decision picks only the default reachability. |
| **D2** | **Which cluster hosts staging today.** | **(A) homelab** — the only cluster with an Argo root, 8 nodes, and NetworkPolicy actually enforced by kube-router, verified empirically (`clusters/instances/homelab/identity.yaml:23-27`) · (B) the OCI `prod` cluster — 2 small ARM nodes holding Vaultwarden, the root of trust; adding N ephemeral namespaces there risks the thing everything depends on · (C) a new cloud cluster — cost. **Recommend A.** It also means "add `eden` to `projects_hosted`" is already done (`identity.yaml:55`). |
| **D3** | **Ratify `New(Config, Deps)` as the library contract**, and pick one lifecycle verb. | **(A) ratify `New(Config, Deps)` and standardise on `Run(ctx) error`** — 14 of 16 libs already have the two-argument shape; only `orchestrator` (`lifecycle.go:23` `Start`) and `agentruntime` (`runtime.go:26` `Run` with two returns) disagree, and both are one-line renames · (B) migrate 14 libs down to `New(Config)` and lose the validated dependency seam. **Recommend A.** It is what the intent asked for, plus the part the code already got right. |
| **D4** | **The survive-or-rewrite ledger.** Ratify or amend. *(Was D5. The old D4 — the prod object store — is retired: see below.)* | **SURVIVES:** all 20 libs; the platformgateway schema, migrations and sqlc layer; the create-saga; `forge`; `gitrepository`; the SvelteKit source; `harnesses/versions.env`; **the whole existing production deploy path** (`release.yml` → the Argo promotion PR, extended by P3-2 to pin the chart revision); every `infrastructure/` contract, chart and cluster file. **REWRITTEN:** the two gateways collapse into `edend`; the HTTP handler surface becomes gRPC + gateway; `projects` leaves JSONB; the frontend loses nginx; `infrastructure/apps/eden/*.yaml` (5 hand-written manifests) becomes the chart, referenced as the **`source` of the same Argo Application**, with `targetRevision` pinned by the promotion PR — the mechanism does not change, only what it points at and what it pins. **ARCHIVED:** `poc/` (933 files, 60 420 lines — `poc/knowledge` alone is 881), `docs/attic/`, `docs/STATUS.md` (self-labelled "DATED JOURNAL — NOT current state"), `deploy/plane/local/`, **the whole of `deploy/servicespec/`** — both renderers, since the chart is hand-written and a generator with one consumer is indirection (**swept after P1's exit proof, not during it**) — and the `gophersys/application-templates` repository (superseded by ADR-0026's fold into `libs`). **NOT CREATED:** `gophersys/template` — eden is the template. |

**Retired: the prod object store decision (formerly D4).** It asked Mateo to
choose between the Oracle bucket and MinIO for a component **no phase touches** —
the whole object-store leg is deferred, the `objectstorage` port already exists
in code, and §5 records the lib as unused by every app. The defence written for
it, "ratifying it now costs nothing", was the tell: a decision that costs nothing
is a decision with no consumer. It has moved into the ledger row that already
carries the leg and its reopening trigger, and it will be made with the writer
that fires the trigger in hand. The terraform state-locking defect that was
riding along in its footnote is now **P0-7**, where a correctness requirement
belongs.

---

## Tempted, not taken — the deferral ledger

The simplicity law, kept honestly. **Deferred is recorded, not deleted.** Each
row names the condition that reopens it; nothing here needs a new decision to come
back, only the stated trigger.

### Designed, then cut, with a reopening condition

| Deferred | Reopens when |
| --- | --- |
| **the FLEET LEG, as one piece** — NATS in the substrate, the `eden-agent` image and its workload, the `launch_supervisor` + `supervisor_ready` saga steps, and the `orchestrator` lib (+ the `Start`→`Run` rename and the ignored `Config` at `postgresstore.go:50`), **and the `nats.jetstream.maxBytes` chart knob** | Mateo schedules the fleet program. The architecture is already decided (agent-fleet rulings, 2026-08-18: role-pods, JetStream planes, frozen envelope, CRD controller); what is deferred is building it, not designing it. **One row on purpose** — pass 1 deferred NATS while keeping the two saga steps that need it, which is how Phase 2 came to assert a supervisor reaching ready over a transport no phase brings up. |
| **the object-store leg** — the PRODUCT's bucket grammar `org/<id>/project/<id>/run/<id>/segment-NNNNNN.jsonl`, content-addressed `artifact/<sha256>`, the 256 KiB inline cap, the prefix-age sweep, `objectstorage` adoption in Go, **and the prod Oracle-vs-MinIO choice** | a step output exceeds the inline cap, or the fleet lands and needs sealed segments. **Not** "staging needs a backup target" — that is CNPG writing to the S3 endpoint homelab already runs (§3.4), which is infrastructure configuration, not this leg. Conflating the two is what made round 1's staging look unaffordable. |
| **THE EVENT-STREAM LEG, as one piece** — an `events` table (migration `0006`), a `WatchProjectEvents` server-stream with `from_seq` resumability, its tick or a LISTEN/NOTIFY replacement, `events.actor`, `events.organization_id` + `events_org_seq`, prod-side pruning, and GitHub/CI ingestion | **the first event producer the product does not itself perform.** v0 has exactly one producer — the create-project run's step transitions — and `workflow_steps` already stores those (§6.1), so an events table would be a second description of one fact and the stream would be client polling with a stream in the middle. Round 5's two named producers (the fleet plane, CI) are each deferred on their own legs; whichever lands first brings this one with it. **One row, replacing five** — the five were facets of a leg that does not exist. |
| **THE ORG COMMAND CENTER's remaining surfaces** — programs, tasks, artifacts, **costs and approvals as product state**. Round 2 defines the product as "programs/repos/tasks/status boards, agent fleets launched and steered from it, artifacts + costs + approvals in one place". Round 6 reordered the first functionality; it did **not** retract that definition, and round 5's rule stands: "everything after is more pages on a proven spine." | each surface, when Mateo schedules its page. **What v0 must not do is foreclose them**: `workflow_runs` and `events` have no home for cost or approval state today, so the first of these to land brings its own columns or its own table. Recorded here because a product definition with no ledger row reads as cancelled rather than as unbuilt. |
| **leader election + `replicas > 1`**, and the lease it needs. `PRIMARY KEY (run_id, step)` prevents a duplicate ledger ROW, not a duplicate `provision_repo` CALL against GitHub. v0 survives at one replica; the two v0 steps also happen to be idempotent at the external system (`forge.go` reads an existing repo back; `steps.go:63-66` converges) — but that is an accident of these two steps, not a property of the design | a measured need for a second replica, or a saga step whose external effect is **not** idempotent. Either one requires a real lease (advisory lock or a `runs.leased_by`+`leased_until` pair) before `replicas` moves off 1. |
| **the `deploy/servicespec` generator** — one typed Go spec rendering the chart | a **second render target** appears. Not a second workload: the fleet leg adds `eden-agent` to the same chart and changes nothing. Nothing in the plan schedules a second target, which is exactly why the generator goes. |
| **a `ListWorkflows` RPC** | the same trigger as the `workflows` table — a kind that carries per-project state. Until then the generated TS enum holds the closed set at build time, and an RPC would be a round trip returning a compile-time constant. |
| **a confirmation on `env down`** — the destructive verb eden actually has. iotea's **production `yes` gate** (withdrawn from the standard; it is not a numbered rule — the live I7 is root discovery) governed a bash-deploys-prod path §3.1 deletes, and nothing replaced it for the verb that destroys a namespace and its volumes | the first accidental `env down`, or the first staging instance carrying data someone minds losing. `--expired` (the CronJob path) must stay exempt whatever is chosen. |
| **eden's remaining Vault surface** — the connectors KEK, harness credentials, the per-team connector store (ADR-0029), and the `vault://eden/<stage>#<field>` reference shape | the fleet leg lands. It is the fleet's credential plumbing, and it migrates to the `secrets` contract (ESO/Bitwarden) **with** it rather than half-now. P0–P3 migrates only what P0–P3 uses: the DSN and barman's `s3Credentials` (§2.4). |
| **`objectStore.retentionDays`** | the object-store leg brings the first non-barman writer. Until then the S3 endpoint's only writer is barman and its retention is `postgres.backups.retentionDays` — a second key would be a second home for one policy. |
| **git-process v2** (pillar 3) | it is a live concurrent deliverable on this machine (`eden-git-process.md`, the four merge conditions in `STANDING-ORDERS.md`). Outside this plan's agent-days, **inside its ship gate** (§0.2). |
| **the coherence super-architect and CI instrumentation** (pillar 4) | round 7 names both and no item builds either. Outside this plan, inside the ship gate. |
| **merge conditions and human gates as enforced process** (pillar 5) | `/dev` lanes exist; the conditions are written in `STANDING-ORDERS.md` and not enforced by a gate. Outside this plan, inside the ship gate. |
| **a Tauri desktop shell** (round 4: "Tauri wrap possible later") | a non-browser client needs the surface. v0 does not foreclose it, but it does not serve it either: the SPA is `go:embed`-served at one origin behind an oauth2-proxy **browser redirect**, and the in-binary JWT is gone — so a desktop shell, like round 5's `ctl`/agent gRPC clients, needs a non-redirect credential path. Reopens with the first non-browser client. |
| **`workflows` as a table** (+ its FK and `UNIQUE (project_id, slug)`) | a workflow acquires per-instance state. The *level* is not deferred — the `WorkflowKind` enum names it, `/w/<kind>` addresses it, and `workflow_runs.kind` groups it (§1.2). Only the row storage waits. |
| **a workflow RAIL in the shell** | the P3-1 co-design wants one — and it will have more than one kind to navigate between. Over v0's single-member set a rail is a label, and committing one now decides layout that round 6 reserves for co-design. |
| **`projects.idea`** | something produces an idea and something reads it — i.e. the fleet leg's supervisor. `CreateProject {org, name}` has no field for it in v0. |
| **`projects.default_branch`** | any code reads it. It holds `main` for every row today. |
| **eden's `.claude/agents/` and `.claude/skills/`**, and the question of which belong in the submodule versus in eden | a second agent or skill needs a home. P1-8 delivers the *connection* round 1 asked for (`settings.json` resolving the submodule's rules); enumerating the tree is separate work, recorded here rather than left absent. |
| **`agentruntime` rework** (dead `var _` at `:155`; `Run(ctx) (TerminationReason, error)` → `Run(ctx) error`, D3) | the fleet leg lands — it is the agent-pod runtime and has no other consumer. |
| **`envelope` rework + the missing `envelopetest` fake** — the one remaining measured violation of round 1's "one fake per external dep" | envelope encryption is first used, i.e. with per-team connectors in the fleet leg. Recorded here so the standard's one open gap stays visible to the plan. |
| **`testing` lib rework** — `New` never returns a non-nil error; the `error` return is vestigial | the lib is touched for another reason. Cosmetic, zero consumers blocked. |
| **scale-to-zero node groups** — `desired_size = 0, min_size = 0` with `lifecycle { ignore_changes = [scaling_config[0].desired_size] }` so the autoscaler and terraform do not fight (iotea `deploy/infra/modules/cluster/nodes.tf:15-19`, `:41-44`) | staging moves to a cloud cluster. On homelab (D2's recommendation) `env stop` is the cost lever instead. |
| **`workflow_steps.ordinal`** | display order must differ from `started_at` order. |
| **`workflow_steps.idempotency_key` as a stored column** | a step's effect is keyed in an *external* system, in which case the column is renamed to say so. |
| **`projects.template_ref`** | a second template exists, or a re-scaffold/update verb is scheduled. |
| **per-project permission grants** (the two-level authorization split) | a second principal exists. Round 5: "multi-user RBAC becomes a schema concern later, not an infra one." |
| **the four audit columns `created_at/by` + `updated_at/by`** | a second actor writes rows. `events.actor` carries provenance where it matters. |
| **`observability.traceSampleRatio` / `logsToLoki` knobs** | a measured observability bill, not a predicted one. |
| **S1 — the pin-bump fan-out** (a job in `.devcontainer/.github/workflows/weekly-bumps.yml` opening a submodule-pointer PR per consumer) | the manual bump is missed twice, or a fourth consumer repository appears. |
| **S2 — `cictl conformance --org` asserting each repo's runner image** against the published digest and the pinned cictl version (#92 risk R4; `libs/.ci/ctl_test.sh:22-23`) | cictl's own C4 lands. It is cictl's roadmap item, not #130's. |

### Withdrawn outright — the premise was false

- **S3, the harness-pin reconciler.** It already exists.
  `.devcontainer/_build/upstreams.txt:118-127` mirrors eden's three harness pins
  through the `eden-manifest` datasource and names eden the one decision point;
  `_ctl/tests/upstream-coverage.test.sh` gates that every pin carries such a row.
- **a `capability:` key per cluster.** Storing a "measured" version in git makes
  it declared, and `clusters/instances/prod/identity.yaml:3-16` is the proof that
  these files describe clusters that are not running.
- **the k3d capability probe as an `infrastructure` CI job.** The repository has a
  twice-written policy against cluster-touching verbs in CI, with the reason
  stated in place (`validate.yml:68-72`).
- **a rebuilt production approval gate.** `release.yml:240-276` →
  `pin-eden-digests.sh` → the Argo promotion PR is already exactly that, already
  reviewed, already auditable.

### Never designed in

- a capability **registry service**, per-capability semver *ranges* in the chart,
  a conformance CRD. (The chart does name the capability *members* it needs —
  §2.2 — because eden uses seven of the eight. A member list is not a range: it says
  which contracts must answer, not which revision of each.);
- an **event-sourcing** core — `events` is an ordered log beside the tables, not
  instead of them;
- a **third render target** for k3d, keeping compose as a permanent fallback, and
  **Tilt / Skaffold** — one chart, one bring-up, one code path;
- **typed prefixed ids** (`o…`, `p…`, `w…`, iotea `libs/id/parse.go:9-20`) — a
  genuinely good idea, but eden's tables are `uuid` and `slug` already carries URL
  identity. Two id schemes cost more than one returns;
- a `propagate` verb in `.devcontainer` — it existed once and was deleted for
  naming a dead path (`.devcontainer/.claude/rules/00-identity.md:1203-1209`).

---

```
┌─ LEDGER #130 · eden rework · blueprint · 2026-08-25 · FINAL · 2026-08-25 ──────┐
│ SHAPE    1 product · 1 role · 1 replica · 1 image · 1 hand-written chart ·    │
│          2 env profiles (+ prod applied by Argo, gate-pinned) · 2 RPCs ·      │
│          6 knobs · oauth2-proxy in front of ALL of them                       │
│ REUSE    org model ✅ saga ✅ charts ✅ contracts ✅ prod deploy path ✅ —     │
│          gRPC is the only new layer. Re-wiring, not green-field.              │
│ FIRST    create a project — eden ITSELF is the template, no new repo.         │
│          provision → seed → `seeded`, then eden onto itself.                  │
│ PILLARS  R7 binds: 1 CI · 2 INFRA · 3 GITOPS · 4 AGENTS · 5 PROCESSES.       │
│          PILLAR work is gated; DOGFOOD-chain work is the goal it enables —    │
│          two categories, not one label (§0.2). Pillar 4 has NO phase item.    │
│          SHIP GATE: all five, not just #92. Items 3/4/5 are outside this      │
│          plan's agent-days and inside its gate (§7 owns the arithmetic).      │
│ L1       8 capability members, 7 annotated, 10 probe assertions. `substrate`  │
│          carries FOUR — storage · namespaces · RBAC · nodes — plus autoscaling│
│          as a contract property. (4 + six members × 1 = 10.)                  │
│ CALLERS  humans · agents · CI — all three now build on ONE `env` code path.   │
│ LOOP     inner `ctl.sh dev` (host, ~2s) vs outer `env up` (cluster) — ONE     │
│          configuration projected from values-dev.yaml. Round 2's named        │
│          "current big problem", absent from every draft until pass 6.         │
│ BOARD    polls ONE unary RPC. No events table, no stream: workflow_steps      │
│          already stores every transition v0 produces.                         │
│ DEFER    the FLEET LEG as ONE piece: NATS · eden-agent · the 2 supervisor     │
│          saga steps · orchestrator. Object-store LEG, command-center          │
│          surfaces, the EVENT-STREAM LEG, replicas>1 + lease, the rail,        │
│          4 pillar components, Tauri. 31 rows, every one with a trigger.       │
│ GATES    10 no-op verbs · a validate that says OK having run only shellcheck  │
│          · 3 pins 214–300 commits stale · 0 of 10 jobs timeboxed · tf state   │
│          locking OFF while its README says ON · L1 never asked for storage    │
│ COST     P0 2.5 · P1 8.25 · P2 6.75 · P3 1.75 = 19.25 agent-days             │
│          §7's trajectory is the ONE home for this arithmetic.                 │
│ NEEDS YOU  4 decisions. D1 tailnet-default + oauth2-proxy · D2 staging=homelab│
│            · D3 New(Config,Deps)+Run · D4 the survive/rewrite ledger          │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Intent coverage — every round, and where it lives

The seven interview rounds, each mapped to the section or ledger row that carries
it. This table replaces nine per-pass narrative sections: the rationale for every
decision now lives in the body section that makes it, and every deferral in the
ledger with its trigger. Where a requirement was cut and later restored, the
restoring home is named — that history is what this table is for.

| Round | Requirement | Where it lives now |
| --- | --- | --- |
| R1 | ONE product, fleet inside | §1.1 · fleet leg deferred as one ledger row |
| R1 | `New(cfg)` + `Run/Close`, no globals, no `init()` | §5 audit · D3 · the two violating libs funded in P1-2 |
| R1 | dev = the WHOLE platform on one machine | §3.5, the six-service substrate · P1-5 |
| R1 | dev serves parallel agents AND interactive sessions | §3.2, dev mints per-caller ids · P1 proof runs two |
| R1 | dev has vault access | §2.4 — the `secrets` contract is ESO/Bitwarden; eden's remaining Vault surface deferred with the fleet |
| R1 | the PR CI environment | P1-9 · profile choice argued in the cell |
| R1 | staging: real security, TLS, `<env-id>` URLs | §3.2 · §3.4 `ingress.host` · D1 |
| R1 | staging COMPACT: full features **with** retention | §3.4 — backups on, observability from the substrate, 7-day retention as the lever |
| R1 | two-level infrastructure contract | §2.2 · §2.3 |
| R1 | prod: exactly one cluster, human approval always | §3.1 (prod is Argo's) · P3-2's digest assertion |
| R1 | terraform state in Oracle, **with locking** | P0-7, proven by contention |
| R1 | spin-up · spin-down · debugging · **STOPPING** | §3.1's six verbs — `stop`/`start` were net-new, never in an early draft |
| R1 | cost optimisation across infra **and dev** | §3.3 — dev's 24 h TTL, the reap step; §3.4's knobs |
| R2 | ORG COMMAND CENTER | §1.2 (orgs→projects→workflows) · the remaining surfaces deferred with a trigger |
| R2 | infrastructure IS the L1 registry | §2.1 · §2.2 |
| R2 | ctl.sh + nx GLOBALLY, common verbs | §4.1 (C·I·V) · §4.2's R-BODY/R-NAME · P0-6 |
| R2 | bash tested, catching everything | §4.1 · P1-7, per-repo suites |
| R2 | **cleanly separate develop and test** | §3.6 · P1-0 — round 2's named "current big problem" |
| R3 | `ctl.sh env up\|down\|ls` minting + TTL + reaper | §3.1 · §3.2 · §3.3 |
| R3 | CNPG everywhere; dev ephemeral, staging 7d, prod backups | §3.4's knob table |
| R3 | MinIO dev/staging, Oracle prod; one S3 interface | §3.4 `backups.destination` · object-store **leg** deferred |
| R3 | migrations applied by a job, never by hand | §6.2 (goose as a library) · P1-3's Job · P2-1 |
| R4 | copy iotea's env model + tooling discipline | §0.1 — three premises measured false, and why |
| R4 | keep the submodule boundaries | unchanged; §4.3's seam |
| R4 | web app, TS frontend served by the Go backend | §1.1 — `go:embed`, no nginx |
| R4 | designed under the ui research framework | §1.2's gate table · P3-1 — census before any layout word |
| R4 | Tauri wrap possible later | ledger row, with its credential-path trigger |
| R5 | ONE protobuf contract; Go **and TS** clients | P1-1 — `buf generate` emits both |
| R5 | tailnet + oauth2-proxy | D1 · the `identity` capability · §3.4 (no `auth.mode` knob) |
| R5 | first slice: one page on a proven spine | Phase 3 |
| R6 | ORGS → PROJECTS → WORKFLOWS | §1.2 · §6.1 — the level is an enum, a route and a grouping key |
| R6 | first functionality: create a project, eden as template | Phase 2 · P2-3 |
| R6 | eden migrates onto itself | P2-5 |
| R6 | per-project UI co-designed with Mateo | P3-1, behind Gate 1 |
| R7 | five pillars, right before eden ships | §0.2 — the map, and the five-part ship gate |
| R7 | DOGFOOD chain | §0.2's diagram |
| R7 | every task maps to one pillar, or is deferred | §0.2 — PILLAR vs GOAL, and pillar 4 has no phase item |

---

## Revision log

Ten adversarial simplicity passes. Each row is the net movement in agent-days and
the one sentence that explains it. The reasoning lives in the body.

| Pass | Date | Total | What moved |
| --- | --- | --- | --- |
| draft | 2026-08-25 | 26 | first blueprint, from the 6 rounds then on record |
| 1 | 2026-08-25 | 14.25 | 33 cuts, applied in parallel without checking the residue |
| 2 | 2026-08-25 | 18.5 | ten of those cuts had removed **requirements**, not work |
| 3 | 2026-08-25 | 17.5 | removed complexity passes 1–2 had themselves created |
| 4 | 2026-08-25 | 17.75 | seams from pass 3's restorations; one real deadlock |
| 5 | 2026-08-25 | 19 | `objectstore` capability, autoscaling, the PR caller, the promotion check |
| 6 | 2026-08-25 | 20 | the CNPG Cluster, the migration Job and the org seed that four sections consumed and no item built |
| 7 | 2026-08-25 | 21.25 | **round 7 found** — the pillar frame, absent from six drafts |
| 8 | 2026-08-25 | 21 | deleted the per-pass measure tables: the seam generator's first half |
| 9 | 2026-08-25 | 19.5 | cut the events table, the stream and its producer — `workflow_steps` already held them |
| 10 | 2026-08-25 | **19.25** | deleted the per-pass narratives: the seam generator's second half. Cut the capability generator and the un-runnable autoscaling half |

**What ten passes established about the method.** Every pass after the first found
the same class of defect: not a bad decision, but a decision whose *neighbours
moved*. Three instruments caught all of them, and none is optional — a ledger row
with a trigger, an exit proof that must be executed, and a count re-derived rather
than carried forward. The fourth, learned late: **grep the set NAME, never the
current value.** A sweep searching for `2 RPCs` cannot find the stale `three
RPCs`; it reports green because it asked the wrong question.

---

## The consumer sweep — the standing instrument

Every numbered set in this document, its authority, and the grep that finds its
consumers. **Run it after the last edit of any change, never before**, and paste
the measurements.

**The grep must name the SET, never the current value.** A sweep searching for
`2 RPCs` cannot find a stale `three RPCs` — it asks the wrong question and
reports green. Grep `RPCs`, `agent-days`, `assertions`, `rows`, then verify each
hit against the authority column. That method is what caught four stale sites in
the final pass that nine earlier value-matching sweeps had walked past.

| Set | Authority | Count | Value-agnostic grep | Hits |
| --- | --- | --- | --- | --- |
| L1 capability members | the eight `contracts/*.md` front-matters | **8** | `capability members` | 3 |
| Members eden requires | the `requires:` annotation, §2.2 | **7** | `annotated` | 10 |
| Probe assertions | §2.3 block | **10** (substrate 4 + six × 1) | `probe assertions` | 3 |
| Chart values knobs | §3.4 table | **6** | `knobs` | 7 |
| Chart objects | P1-3 | **7** | `Objects: \`Chart` | 1 (enumerated: 7) |
| C-rules · I-rules · V-rules | §4.1, §4.2 | **10 · 7 · 5 names/3 classes** | `C1–C10` · `I1–I7` · `V1–V5` | 3 · 3 · 3 |
| RPCs in v0 | §1.2 | **2** (surface reads through 1) | `[a-z] RPCs` | 3, all reading two |
| `env` verbs · profiles | §3.1 · §3.4 | **6 · 3** | `Six verbs` · `three profiles` | 2 · 2 |
| Migrations | §6.1 | **1** (`0005`) | `migration \`000` | 6 |
| Schema v0 tables | §6.1 | **8** | `tables in schema v0` | 1 |
| Ledger rows | the deferral table | **31** | `[0-9]+ rows` | 3, one live |
| Decisions | §8 | **4** | `[0-9] decisions` | 2 |
| Pillars | §0.2 | **5** | `five pillars` | 6 |
| Phase items | §7 | P0 **7** · P1 **10** · P2 **6** · P3 **2** = **25** | `^\| \*{0,2}P[0-3]-[0-9]` | 25 |
| Agent-days | §7 trajectory | **19.25** = 2.5 · 8.25 · 6.75 · 1.75 | `[0-9.]+ agent-days` | 7, each a phase figure or the total |

Measured after the final edit of pass 10 — **including the edit that wrote this
table**, which is itself a consumer of eight of these sets. Nine of the counts
moved between the pre-append and post-append measurement; the post-append figures
are the ones above. A sweep measured before the last edit certifies a document
that no longer exists.
