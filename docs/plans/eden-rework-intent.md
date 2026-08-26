# eden rework — design intent (interview record)

Round 1 — 2026-08-25. Mateo's answers, structured but faithful.

## Identity
ONE product, fleet inside. The UI/backend/schemas are the surface; the agent
fleet is the engine room. One repo-of-record, one deploy-unit set; the fleet
is consumed as internal services.

## Library contract
Every lib: `New(cfg Config) (*T, error)` — no globals, no `init()`, cfg
validated at construction — plus `Run(ctx)`/`Close()` lifecycle where the lib
does work. Same binary scales BOTH axes: goroutine pools in-process AND k8s
replicas horizontally; instances cheap, share-nothing. Testing standard:
table tests + race detector + one fake per external dep.

## Environments (his words, structured)

### dev
- A devcontainer instance; eden is developed INSIDE it.
- Two users of dev: (a) agents in parallel workflows AND us in daily
  interactive sessions (with vault access); (b) the PR CI environment —
  solving issues, revising code, running tests.
- eden's `.claude/` must be 1:1 connected and leverage the `.devcontainer`
  submodule.
- dind / local k3d (or similar) runs the WHOLE platform as a single-instance
  deployment on one machine — backend + UI + databases + everything —
  "exactly how iotea dev worked".

### staging
- k8s + helm charts, the whole thing, real security + TLS + certificates.
- URL format: `<unique-env-id>.<whatever>.url.com` → MULTIPLE instances,
  each with a unique env id.
- Runs on ANY kubernetes cluster ⇒ TWO-LEVEL INFRASTRUCTURE CONTRACT:
  - L1: the cluster itself — autoscaling, nodes, namespaces, RBAC, ALL of it
    — versioned as a capability.
  - L2: helm charts declare "requires infrastructure version >= X".
  - Result: deployable on k3d single-machine, full AWS, DO — same charts.
- Staging is COMPACT: full features (observability, backups) but with a
  configurable retention (~7 days) so it does not eat resources. A
  pre-production balance, not costly.

### production
- Exactly ONE kubernetes cluster instance, local or cloud — never more.
- Terraform state in the Oracle bucket; concurrent workflows/agents on the
  repo must not conflict (state locking).
- Deploy ALWAYS requires human approval: human inspects the staging that is
  to be released, QA, then promote or change.

### agents
Full access to their OWN dev or staging instances as they wish.

### The stated goal
Best balance between development speed and thorough testing/QA. Spin-up,
spin-down, debugging, STOPPING staging — cost and time optimization of the
utmost importance across all infrastructure and dev environments.

## Open threads (next rounds)
- Product surface: what the UI/backend v1 actually does (schemas depend on it).
- Staging lifecycle: who mints env-ids, PR-triggered vs CLI, TTL enforcement,
  which cluster hosts them today.
- Infra-contract home: is the infrastructure repo the L1 capability registry?
- Datastores: CNPG vs managed postgres; MinIO vs Oracle bucket for objects;
  migration tooling.
- iotea: what it got right (copy) and wrong (avoid).

## Round 2 — 2026-08-25

### Product v1
ORG COMMAND CENTER: the surface for running the org — programs/repos/tasks/
status boards, agent fleets launched and steered from it, artifacts + costs +
approvals in one place. Persistent, visual, multi-session version of what the
chat sessions do today.

### L1 contract home
gophersys/infrastructure IS the L1 capability registry: a versioned manifest
of what a compliant cluster provides (core set, RBAC shapes, storage classes,
cert-manager, observability endpoints). eden's charts pin `requires: infra
>= vX`. CI-checkable in both directions.

### Monorepo + toolchain intent (his words, structured — given in place of
### the staging-lifecycle answer, which is RE-ASKED in round 3)
- eden is a MONOREPO; leverage ctl.sh + nx GLOBALLY for all projects.
- Common verbs, simple clean style, TRUE abstraction layers.
- Toolchain dependency = what the devcontainers provide (1:1).
- Bash written like iotea's: errors always raise, clean functions, a main
  function, well documented, tested, catching everything.
- Applied globally to all submodules with ONE assumption: ctl.sh is callable
  standalone in each submodule's CI, OR nx drives it inside the monorepo —
  and the monorepo is where most development happens.
- The hard coordination problem, named: tool updates and requests must move
  cohesively at once WITHOUT breaking parallelism.
- The current big problem, named: cleanly separate develop and test without
  losing speed or adding complexity. "We really have to create really clean
  abstraction layers."

## #92 proposal — key facts (full doc: scratchpad/cictl-org-contract-proposal.md)
- MEASURED: the reusable pr-review.yml has ZERO callers and CANNOT be called —
  job_workflow_sha is empty in a called workflow (#46 confirmed), the pin
  guard correctly kills every run. 3 divergent 106-line copies drift instead;
  research-ui checks out cictl UNPINNED; a .devcontainer test exemption rests
  on the dead mechanism.
- D1 rec: composite action gophersys/cictl/review@<sha> + GENERATED caller
  (pin cannot be wrong; generation ends drift).
- D2 rec: tier review budgets — platform/module repos opus/$25/4 rounds;
  research/tooling sonnet/$10/2.
- D3 rec: org conformance REPORTS (scheduled board), per-repo drift still
  blocks that repo's own PRs.
- P0 = ~10h closing #44 (libs 2h, eden 1h after cictl's 5 build items).
- Blockers: eden .ci/ctl.sh 4 verbs return 0 when nx absent (fix first);
  cictl/hnslint/review are PUBLIC repos — arc-review refuses public repos,
  needs a runner-group decision.

## Round 3 — 2026-08-25
- Staging lifecycle: `ctl.sh env up|down|ls` verb (nx-wrapped in monorepo)
  mints env-ids + deploys + stamps TTL; a reaper destroys expired instances.
  ONE code path for humans, agents, CI. Nothing implicit; PRs call it
  explicitly.
- #92: APPROVED as recommended (composite action @sha + generated callers,
  tiered budgets opus-$25/4 platform vs sonnet-$10/2 research, conformance
  reports + per-repo drift blocks). Build launched 2026-08-25.
- Datastores: CNPG operator everywhere (dev ephemeral, staging 7d-compact,
  prod full backups→Oracle bucket); objects = MinIO in dev/staging, Oracle
  bucket (S3 API) in prod — one S3 interface in code; migrations = versioned
  SQL in-repo (atlas or goose) applied by a job, never by hand.

## Round 4 — 2026-08-25
- iotea: COPY the environment model + the tooling discipline (the bash/verb
  standard). The three-env flow is the reference implementation, not just a
  concept.
- Repo shape: KEEP the submodule boundaries (infrastructure, libs,
  .devcontainer under eden; tooling repos outside). The coordination problem
  is solved by the global ctl.sh+nx toolchain layer + the cictl contract —
  tooling makes them move cohesively, not repo-merging.
- UI: WEB APP — TypeScript frontend served by the Go backend, designed under
  the ui research framework (boards-not-prose as a product principle),
  tailnet-reachable, one deploy unit. Tauri wrap possible later.

## Round 5 — 2026-08-25 (top-level interview COMPLETE)
- API: gRPC core + HTTP gateway. ONE protobuf contract as source of truth;
  gRPC between services and for ctl/agent clients; gateway (grpc-gateway or
  connect) exposes REST+JSON for the web UI from the same definitions; typed
  clients generated for Go and TypeScript.
- Auth: tailnet + oauth2-proxy (the secrets/notes pattern). Single user now;
  multi-user RBAC becomes a schema concern later, not an infra one.
- First vertical slice: LIVE ORG STATUS BOARD — one page: UI → gateway → Go
  backend (New(cfg) services) → postgres (first real schema) + live fleet/CI
  events, rendered under the dense-UI framework, deployed dev→staging→prod
  through the full env machinery. Everything after is more pages on a
  proven spine.

## Round 6 — 2026-08-25 (Mateo, unprompted refinement — SUPERSEDES parts of round 5)
- SIMPLICITY IS THE LAW: "less is always more" — the blueprint gets multiple
  adversarial review/architecture runs whose only question is "what can be
  removed or simplified".
- ORGANIZATIONAL MODEL comes from iotea's UI: ORGS → PROJECTS → WORKFLOWS.
  That hierarchy is the basic organizational structure — "probably the
  easiest way to set up the basic organizational stuff".
- FIRST FUNCTIONALITY (supersedes the round-5 status-board-first order):
  CREATE A NEW PROJECT. Eden itself is the template — a new project is
  scaffolded "based on how eden works". Then: the first migration is EDEN
  ONTO ITSELF (eden becomes the first project inside the product).
- The main per-project UI (what a user interacts with when USING a project)
  is developed TOGETHER with Mateo afterward — co-design sessions, not
  delegated wholesale.

## Round 7 — 2026-08-25 (Mateo: THE PILLAR FRAME, binding priority)
FIVE PILLARS, insanely priority, must be absolutely right BEFORE eden ships,
because eden IS the foundation that runs inside the production deployment:
1. CI          (cictl contract, tiers, gates, measured lanes)
2. INFRASTRUCTURE (images, runners, envs, L1 capability contract)
3. GITOPS      (git-process v2, artifact promotion, pointer discipline, Argo)
4. AGENTS      (review tiers, coherence super-architect, CI instrumentation,
                fleet)
5. PROCESSES   (/dev lanes, merge conditions, human gates — binds the rest)
THE GOAL: DOGFOOD. The pillars get hardcoded → eden is created as a project
from its own template → eden migrates onto itself → the platform develops
itself. Every open task maps to exactly one pillar; work that serves no
pillar is deferred.

## FINAL RULINGS — Mateo, 2026-08-25 ("ok go with the recommended")
Blueprint CERTIFIED at 19.25 agent-days after 10 adversarial passes.
All 4 decisions = as recommended:
- D1 domain+auth: tailnet + oauth2-proxy, no auth knob.
- D2 staging host: the homelab k3s cluster.
- D3 library contract: New(Config, Deps) + Run(ctx)/Close.
- D4 survive/rewrite ledger for the 8 REWORK libs as filed.
EXECUTION ORDER: P0 (gates real, 2.5d) starts AFTER eden PR #14 lands
(same repo; fixture + harness fixes are pre-P0 gate work). Then P1 env
machinery, P2 create-a-project (eden as template), P3 board co-designed
with Mateo. Ship gate: all five pillars.
