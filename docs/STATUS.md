# Eden build STATUS — autonomous manager loop

> Living working-state for the self-paced manager loop (set up 2026-06-12 while Mateo is away).
> This is my memory across loop iterations. Mateo: read this first when you're back.

## Goal (definition of done)

1. Every `libs/go/` library implemented from its frozen contract; gates green (gofmt, vet,
   `go test -race`); uniform per 10 §6.1; conformance suites pass.
2. Substrate/integration libraries have REAL integration tests (docker daemon + k3d cluster,
   never mocks) that pass.
3. Apps in place: `apps/frontend` (chat + document workspace) + the backend agent-session
   service, wired to the `agentsession` contract. Chat UI: server-triggered sequence-numbered
   events, full telemetry taxonomy, lossless start/stop/resume, drill-down to any session —
   built + tested with a FAKE harness adapter end-to-end. Real claude-code adapter wired but its
   authenticated run is **gated on Mateo's `setup-token`** (I cannot mint it).
4. Playwright forced-CRUD E2E lane green (create through UI → destroy through UI before exit;
   nested creation covered).
5. Every implementation wave followed by the mandatory ADR-0017 review-and-architecture wave
   (cohesion + true-coverage + adversarial), findings fixed before proceeding.
6. Working tree clean; HTMLs regenerated; no scratch; servers killed; libs submodule pushed +
   pointer bumped; eden pushed.

## Current state (updated each milestone)

- **Wave 3A** ✅ COMPLETE + COMMITTED (2026-06-13): all six pattern libraries green
  (unit + conformance, go vet + go test -race) — errors, dependencies, configuration, testing,
  secrets, observability. Submodule commit f076942 on origin/main; eden pointer bumped; the three
  new contracts (workspaceprovider, gitrepository, orchestrator) committed. Latent standards
  violations remain (e.g. configuration imports configurationtest under the banned alias
  `cfgtest`) — these are the conform target of 3A.5, not bugs.
- **Wave 3A.5** ✅ COMPLETE + COMMITTED + PUSHED (2026-06-13): enforcement layer built and the six
  libs conformed (golangci-lint 0 issues, hnslint clean, govulncheck clean, gofumpt clean, go test
  -race green). libs submodule 7daeeeb on origin/main; eden ce4a158 (hooks + hnslint + pointer).
  Three real gate bugs were caught by dogfooding the hook on its own commit and fixed: golangci
  --fast-only disarmed forbidigo (now full set); testdata fixtures were being linted (now skipped);
  standalone modules broke under the workspace (libs/go/* use go.work, others GOWORK=off). Hooks
  active (core.hooksPath=.githooks); a staged `cfg:=3` is now blocked — verified.
- **Notion frontend** ✅ COMPLETE + COMMITTED + PUSHED: apps/frontend rich block renderer + reading
  shell (outline/scrollspy, tier nav, breadcrumbs) on the Eden tokens + projection seam.
- **ADR-0017 review wave** ✅ COMPLETE + COMMITTED (libs 89f90f3): found real value —
  a JSON stack-overflow DoS blocker in configuration (now bounded at maxJSONDepth=256 + regression
  test), plus coverage/correctness fixes in dependencies/testing/secrets/observability. Caught that
  the review fixers themselves introduced regressions (errors contract drift CANCELED->CANCELLED →
  reverted; testing/observability lint) — fixed before commit. All six green (golangci 0, race 0).
  Note: golangci is non-deterministic across the shared workspace under parallelism — run the gate
  sequentially/isolated (the hooks already do; CI lanes must too).
- **Wave 3B: workspaceprovider** ✅ DONE + COMMITTED + PUSHED (libs ed65211 on origin/main, eden pointer bumped):
  F1 substrate port + docker + kubernetes(k3d/kind) adapters, FULL security/credential plane real + non-vacuously
  tested. B1-B8 ALL resolved: B1/B2 real docker --internal default-deny + real dial-out conformance; B3 real
  ConflictError; B4 real all-or-nothing + resource-limit; B5 contract amendment (§7 Q13 *Provisioner); B6
  MountSecret real material on BOTH adapters (weaken-proven non-vacuous on docker+k3d); B7 k8s dockerconfigjson +
  ImagePullSecrets, real registry:2+htpasswd end-to-end on docker AND k3d-in-cluster (docker positive case
  de-vacuoused: purges the local tag so success truly exercises auth — weaken with a wrong password FAILS); B8
  resource-limit binds on real cgroup (docker+k3d), OOM discriminator delivered on docker, honestly OD-15 on k8s.
  Verified MYSELF on real substrates (never trusting agent green): docker suite green, kind suite green, k3d suite
  green SERIALIZED. RELIABILITY FIX: TestK3d_Conforms/TestKind_Conforms now serial (no t.Parallel) — two real
  clusters serving the full suite at once flaked the k3d serverlb ("connection refused"); serialized → both green.
  The credential-wave workflow w3t0n08sj (62min, 2 agents) corroborated; its one material residual (docker B7
  positive vacuousness) is FIXED; two minor robustness/process notes were truncated in its result and the
  transcript was cleaned — revisit in the ADR-0017 review wave. NOTE: orphaned pre-compaction verification
  subagents from this workflow thrashed the host + transiently weaken-edited credential.go (self-reverting) — all
  drained without killing any claude PID; see the straggler section below.
- **Wave 3B: workspaceprovider (historical)** — F1 substrate port + docker + kubernetes
  (k3d default, kind 2nd target) adapters; workspaceprovidertest conformance suite. REAL integration
  tests spin actual containers + an ephemeral k3d cluster and pass leak-free (TestK3d_Conforms ~48s,
  16 conformance cases, cluster auto-deleted). Took 3 sub-waves (substrate is hard; agents
  over-reported each time — caught by my own gate runs). go.work now includes workspaceprovider
  (gitignored — fresh clones/CI need `go work use ./libs/go/workspaceprovider`).
  ⚠️ The original wave's review (completed 98min late, after I committed bc017cc) found BLOCKERS the
  green gates missed: (1) docker adapter declares CapEgressPolicy=CapPartial but ignores spec.Egress
  entirely — faked security capability, untruthful manifest; (2) the egress fail-closed conformance
  case asserts only behind `if isFake` (cases.go ~365-395) — the default-deny security property
  (07 §3) is real-tested by NOTHING but the fake on docker/k3d/kind (a smoke); (3) idempotency drops
  the incompatible-spec→ConflictError half (substrate.go findExisting + cases.go caseIdempotency);
  (4) all-or-nothing rollback + resource-limit OOM conformance are fake-only/skip on real substrates;
  (5) exported surface adds Connection/RunDriver/Probe/Provisioner + New returns *Provisioner not
  *Substrate (a genuine frozen-contract defect: Substrate name collision) — ratify as a contract
  amendment. A security-hardening fix wave is addressing 1-4; 5 needs a contract amendment.
- **NEXT: Wave 3B cont.** — agentsession (F4) → orchestrator v0 → chat UI → Playwright E2E
  (+ doc-13 branch hook + merge agents).
  - **BUILD-ORDER CORRECTION (2026-06-13):** the loop's stated order (orchestrator → agent-session) is
    INFEASIBLE — orchestrator imports the agentsession package extensively (Spec×8, Session×4, Factory×3,
    TokenLedger, State, Budget, Event, …) and cannot compile without it. So the dependency-correct order is
    **agentsession (F4 library) FIRST → orchestrator (consumes agentsession + workspaceprovider) → chat UI
    (consumes the agentsession Event stream + orchestrator) → Playwright E2E.** agentsession is also the
    keystone the chat UI needs (the server-triggered Event stream). Building it first.
  - **agentsession sub-wave IN PROGRESS** (workflow build-agentsession, task w1zqzprbj / run wf_16d84369-a55,
    Opus impl→adversarial-verify). Builds: Session primitive (Open/Prompt/Steer/Abort/state/Close, one
    primitive no mode-fork), the normalized Event taxonomy with MONOTONIC per-session Seq (the one mechanism
    for Last-Event-ID reconnect / fresh-tab replay / FromSeq(0) fold / multi-client fan-out — race-clean),
    tool-grant + host-tool + PermissionRequest/Decision, TokenLedger, credential/setup-token seam. A
    DETERMINISTIC fake harness drives the full path end-to-end + the REAL claude-code adapter WIRED-but-GATED
    on Mateo's setup-token (NOT minted, no live auth, never touch ~/.claude). On completion VERIFY MYSELF:
    full gate + integration -race (concurrent multi-client tailing CLEAN), weaken Seq/replay/fan-out/Steer/
    Abort/credential-leak/ledger to confirm non-vacuity, confirm real adapter gated-not-executed. Then commit
    + push + bump eden pointer. Do NOT run conflicting work in libs/go/agentsession while it runs.
  - **gitrepository sub-wave ✅ DONE + COMMITTED + PUSHED** (libs f3cb2c1 on origin/main; eden pointer bumped).
    Built by workflow build-gitrepository (wrfc58xu8, Opus impl→adversarial-verify, ~53min). Three consumer
    ports under the 5-method ceiling — Provisioner (Clone/AddWorktree/RemoveWorktree), Inspector (Status/Diff/
    Branches/Worktrees), Author (Stage/Commit-with-Identity/Fetch/Push) — over a pure New(Config,Deps) spine +
    a 5-method Backend vendor seam. Structurally NEVER a merge engine (no Merge/Rebase/CherryPick/Pull/Reset/
    Force verb, no PushOptions.Force); Pull = Fetch + ff-only Push → NonFastForwardError(both tips). Commit
    stamps Author identity (ActorAgent → Eden-Run/Session/Phase trailers; human → none). Credentials ride a
    secrets.Reference resolved at the op into a per-op 0600 credential-helper script via Secret.Use — never
    argv/URL/config/log/Error. Default SystemGit backend shells real git 2.50.1; gitrepositorytest = in-memory
    fake + ONE 13-property conformance suite BOTH backends pass + real integration over actual git + real
    worktrees + a real local bare remote. The workflow's verify agent ran 7 weaken/revert non-vacuity proofs.
    I VERIFIED MYSELF on the settled tree: all 7 gates green (gofumpt, golangci 0 default+integration alone,
    hnslint, vet both, race, integration -race on real git), leak-free (cred temp dirs before=after=0), and my
    OWN weaken on the crown-jewel ff-only-push property (injected --force) made BOTH the conformance + real-
    bare-remote tests FAIL ("divergent Push must be NonFastForwardError, got nil") — reverted, green again.
    Contract compiled as written (no §7 amendment). Removed the empty internal/ dir. No stragglers this time
    (let the workflow finish before verifying — the lesson held). Contract docs/architecture/contracts/gitrepository.md (draft; amendments
    surface as Qs like workspaceprovider Q13/Q14). Three ≤5-method interfaces: Provisioning (Clone/AddWorktree/
    RemoveWorktree), Inspection (Status/Diff/Branches/Worktrees), Authoring (Stage/Commit-with-Author/Fetch/
    Push). NO merge engine; fast-forward-only; NonFastForwardError/ConflictError = escalate-to-gate signals;
    secrets.Reference resolved server-side (never logged, 07 §2); operates over a Workspace path. Lands in
    libs/go/gitrepository/ + gitrepositorytest/; module github.com/gophersys/libs/go/gitrepository; needs
    `go work use ./libs/go/gitrepository`. Real-substrate tests = REAL git + a real local bare remote for
    Push/Fetch + real worktrees, behind //go:build integration. Under enforcement (golangci 0 alone, hnslint,
    gofumpt, race). The workflow does NOT commit — I verify myself + commit after. WHEN it completes: run the
    settled gate + integration MYSELF, weaken-to-confirm-non-vacuous, then commit to libs + bump eden pointer.
- **New directives captured 2026-06-13** (intake C26/C27, REQ-0027/0028, doc 13, ADR-0019):
  - **Git workflow standard** (doc 13) — one workflow machine for docs/architecture/implementation;
    branch/commit grammar; worktrees; merge agents. TOOLING (branch-name hook + merge-agent role)
    builds in Wave 3B/3C; the standard is binding now.
  - **Notion-grade frontend** (REQ-0028) — launching in parallel now (apps/frontend only; no
    collision with 3A.5).
- Done earlier: docs (00–12 + ADRs 0001–0017), document system + validator, frontend v0 (document
  workspace, Eden visual identity C21), agentsession contract, REQ-0001..0024.

## Next actions (my detailed plan — survives loop iterations)

When Wave 3A completes:
1. **Triage** — run gates myself (`go vet`, `go test -race` over libs/go, `gofmt -l`). Fix the
   known `configuration` break: `conformance_test.go` references undefined `cfgtest.Run` /
   `cfgtest.NewParser`; `cfgtest` is a banned abbreviation → must be `configurationtest`. Triage
   the verify agent's other deviations. Dispatch an Opus fixer for anything non-trivial.
   (NOTE: a transient workspace build inconsistency was observed mid-wave — dependent libs'
   go.mod requiring errors@v0.0.0 while being written; clears when 3A finishes; `GOWORK=off`
   isolates. Confirm the whole workspace builds clean post-3A.)
2. **Commit** — commit the six libraries into the `gophersys/libs` submodule, push it; bump the
   submodule pointer in eden; push eden (the three new contract drafts; go.work is gitignored).
3. **Wave 3A.5 — ENFORCEMENT (ADR-0018, C25): build the enforcement layer before the review.**
   Toolchain is already installed (golangci-lint, gofumpt, govulncheck, gorelease, staticcheck).
   Build: the shared `libs/.golangci.yml` (curated strict config — interfacebloat=5, ireturn,
   errcheck/wrapcheck/errorlint, forbidigo banned-token gate, depguard import boundaries, revive,
   etc.); `tools/hnslint` (structural HNS-1 check); the breaking-change gate (gorelease); wire all
   into each library's `ctl.sh` + a tracked `.githooks/` (pre-commit/pre-push) + `.ci/`; build the
   `libs/plugins/project-go` Claude Code plugin (SessionStart contract+rules injection, PostToolUse
   per-file lint, PreToolUse commit gate) + `libs/.claude/rules/`. Run it mechanically against the
   3A libraries and **conform them** (this is where `cfgtest` and friends get caught for real).
4. **Review wave** (ADR-0017, all agents Opus) — now consumes the linter output as its substrate:
   architecture cohesion vs contracts + 10 §6.1; true-coverage audit (flag mock-only/no-shortcut
   violations; list which libs owe real docker/k3d integration tests); adversarial correctness.
   Fix findings.
5. **Verify** green again (gates + enforcement clean); update this STATUS.
6. **Wave 3B (develops UNDER enforcement from birth)** — substrate adapters (docker + k3d, real
   integration tests), git operations, orchestrator v0, agent-session backend service, chat UI,
   Playwright forced-CRUD E2E. Then its review wave. Then verify.
7. Final cleanup + DONE check → push a notification to Mateo.


## Hazards observed

- **Orphaned subagent stragglers:** after a workflow reports complete, some
  `claude --dangerously-skip-permissions` subagents can keep running and write files
  asynchronously (observed: a review-wave errors fixer wrote errors.go ~minutes after the wave
  reported done, re-dirtying a committed tree). MITIGATION: after a wave, before committing, wait
  for file mtimes to stabilize and re-run the full gate on the settled state; let the gate decide
  keep-vs-revert. Do NOT kill claude processes (one is the main session; others may be Mateo's
  terminals — killing is destructive). errors settled green and is integrated (libs feb0c57).

## Blockers / needs-Mateo

- **setup-token** (REQ-0021): the real claude-code authenticated agent run needs Mateo to run
  `claude setup-token` once interactively. I build and test the full path with a FAKE harness
  adapter; the real adapter is wired but its live run waits for the token. NOT a loop-stopper.

## Cleanup ledger

- Render toolchain lives at `/tmp/eden-render/node_modules` (marked, mermaid, jsdom) — used by
  `docs/tools/*.mjs` via `NODE_PATH`. Consolidate into repo `node_modules` via root `yarn install`
  once safe (deferred while the frontend's install is in flight). Tracked so it's not forgotten.

## workspaceprovider — consolidated blocker ledger (all 3 reviews, 2026-06-13) — ✅ ALL RESOLVED (libs ed65211)

RESOLUTION: every B1-B8 below is now really-implemented AND really-tested on a real substrate (or honestly
declared CapAbsent + contract-amended). Verified independently on real docker/k3d/kind, non-vacuously (weaken
probes), leak-free. Committed ed65211 + pushed; eden pointer bumped. The per-item history is kept for the record.

Lifecycle/exec/files/teardown plane: REAL + green + leak-free (k3d conformance 48s, docker+k3d+kind).
Security/credential/OOM plane (was FAKED — NOW REAL):
- B1 docker egress CapPartial declared, spec.Egress never read (faked capability) → impl real OR CapAbsent
- B2 egress fail-closed conformance asserts only `if isFake` → make REAL on declared substrate, or honest SKIP for Absent
- B3 idempotency: incompatible-spec re-Provision never yields ConflictError (findExisting does no spec compare)
- B4 all-or-nothing rollback + resource-limit OOM conformance fake-only/skip on real substrates
- B5 surface drift: Connection/RunDriver/Probe/Provisioner + New→*Provisioner not *Substrate (Substrate name
  collision = genuine frozen-contract defect) → ratify as contract amendment
- B6 MountSecret credential material DROPPED on both adapters (resolved.Mounts consumed by no one → empty file)
- B7 k8s adapter ignores resolved.PullSecret (no dockerconfigjson, no ImagePullSecrets) → private pull can't auth;
  adapters NOT substitutable on credential seam
- B8 OOM RunStatus.Condition structurally never delivered on real path (Run=exec into hold container)
Hardening wave wxgxfvuvx covers B1-B5. NEXT iteration must also fix B6/B7 (credentials = crown jewels, 07 §2 —
really-implement, not deferrable) and decide B8 (honest CapAbsent + deferred, or restructure Run).
DECISIVE RULE: every declared capability is really-implemented AND really-tested on a real substrate, OR
declared CapAbsent + gap recorded + contract amended. No fake-passes, ever.

### B6/B7/B8 real-substrate verification (2026-06-13, this loop) — POSITIVE, one re-run pending

Ran the settled gate WITH the workspace + the real integration suites myself (never trusting agent green):
- Unit gate: gofumpt 0, go vet clean, `go test -race ./...` green; golangci-lint 0 issues (default tags AND
  `--build-tags integration`).
- **docker integration suite (`-tags integration ./dockeradapter/...`): FULLY GREEN.** B6
  MountSecretMaterialReachesWorkspace, B1/B2 EgressDefaultDenyDeclaredAllow + TestDocker_DefaultDenyEgress,
  B8 ResourceLimitsBind + TestDocker_ResourceLimitsBindOOM, B7 TestDocker_PrivateImagePullSecret all PASS
  (TestDocker_Conforms 43s; TenancyIsolation honest-skips CapMultiTenant absent).
- **B6 non-vacuity PROVEN**: weakened the docker adapter's MountSecret write to emit `WRONG-WEAKEN-PROBE`;
  caseMountSecret correctly FAILED (`content = "WRONG-WEAKEN-PROBE", want the seeded secret value`); reverted.
  The test reads adapter-written content — not a vacuous pass.
- **B7 non-vacuous by construction**: WITH pull-secret → authenticated pull SUCCEEDS; WITHOUT → ImageError
  (Kind=Invalid, *ImageError in chain), password never in the message. Real registry:2+htpasswd, real push/pull.
- **kind integration suite: FULLY GREEN** — all 17 conformance cases incl. MountSecret, SecretMaterialNeverLeaks,
  ResourceLimitsBind, TenancyIsolation, StateNormalization (TestKind_Conforms 53s).
- **k3d**: TestK3d_ProvisionRunExecFilesTeardown PASS (19s); **TestK3d_PrivateImagePullSecret PASS (34s) — B7 real
  on a real cluster** (dockerconfigjson Secret + ImagePullSecrets objects present; in-cluster authed pull works
  WITH, ImageError WITHOUT); TestK3d_Conforms credential/security cases all PASS (MountSecret, SecretLeak,
  ResourceLimitsBind, ManifestTruthfulness). ⚠️ ONLY the two NON-credential cases TenancyIsolation +
  StateNormalization FAILED, with `dial tcp 0.0.0.0:5xxxx: connection refused` — the k3d apiserver/serverlb
  went unreachable mid-run. ROOT CAUSE: host resource contention — K3d_Conforms and Kind_Conforms both carry
  `t.Parallel()` so TWO real clusters ran the full 17-case suite concurrently, AND orphaned pre-compaction
  stragglers were ALSO running docker-conformance loops at the same time (see below). The same two cases pass
  on docker AND kind. NOT a code defect — a parallel-cluster reliability flake.
- **TODO before DONE**: (a) re-run TestK3d_Conforms ALONE on a quiet host → expect green (confirms flake); 
  (b) HARDEN: drop `t.Parallel()` from the two heavyweight cluster conformance tests (K3d_Conforms,
  Kind_Conforms) so two real clusters never serve the full suite simultaneously — the brief values reliability
  of the real-substrate lane; running two clusters in parallel on a laptop is inherently fragile.

### STRAGGLER hazard hit HARD this loop (the documented orphaned-subagent problem, post-compaction variant)

Multiple orphaned background processes from BEFORE the compaction survived as live OS processes that TaskList
no longer tracks. Identified and handled WITHOUT killing any claude process or Mateo's terminals:
- A finite `for run in 1 2 3; do go test ... TestDocker_Conforms; done` LEAK-CHECK loop (pid 13240, a child of
  my own session) — repeatedly spun docker conformance. Finite; it exited on its own / I reaped its last
  go-test children. Pure go test, no edits.
- A B6 WEAKEN-VERIFY actor doing exactly the value=nil→test→revert non-vacuity cycle on credential.go. The
  harness system-reminder caught it mid-cycle (line 108 transiently `value = nil // TEMP-WEAKEN`); it
  SELF-REVERTED within seconds (verify-then-revert is well-behaved). credential.go confirmed CLEAN afterward.
- These stragglers' container/cluster churn is what tipped the k3d conformance into the apiserver flake above.
MITIGATION APPLIED: never kill claude PIDs (my session is pid 38821 under the VS Code terminal; confirmed via
PPID); only reaped stray `go test`/`*.test` OS processes; left the vite preview server (pid 14072, port 4173)
and `caffeinate` alone for Mateo. Running a whole-tree mtime-stability watch before committing (the playbook:
wait for mtimes to settle, re-run the gate on the settled state, let the gate decide).
