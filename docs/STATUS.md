# Eden build STATUS — autonomous manager loop

> ⚠️ **DATED JOURNAL — NOT current state (banner added 2026-07-06).** This was the self-paced
> manager loop's working memory (2026-06-12 → 2026-06-14) and stops at Milestone B. It predates —
> and therefore omits — the permission system (ADR-0025), the editor system (ADR-0027),
> `platformgateway` + login, `libs/go/forge` + the project-creation saga, `codeinsight`, the
> templates-into-libs fold (ADR-0026 — any "4th submodule" claim below is WRONG), and the projects
> dashboard. Kept as a build record; for current state read the git log and the architecture
> ADR set (0020–0027).

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

## ▶ ACTIVE PROGRAM (2026-06-13 cont.) — multi-harness agent platform, devcontainer-first, REAL tests no mocks

Mateo returned, gave the live claude setup-token + an OpenRouter key, and opened a big program. Plan:
`~/.claude/plans/groovy-growing-puppy.md`. Locked decisions in memory `harness-platform-architecture`.
Credentials live in gitignored `.env.development` (the `.env.example`/`.env.<environment>` standard; real
values NEVER committed); `deploy local` loads them + seeds the local REAL Vault IOTEA-style. (Migrated off
the old `.dev-secrets/` dir, 2026-06-13.)

PROGRESS (foundation, all committed + pushed across eden + libs + .devcontainer, pointers bumped):
- ✅ **Both real harnesses fixed + verified INSIDE the devcontainer**: claude 2.1.177 live test 1.9s,
  omp 15.12.4 live test 4.0s (real OpenRouter/DeepSeek), race-clean. The claude `-p`/Ready-handshake fix
  and the omp `--mode json` one-process-per-turn adapter both green.
- ✅ **ADR-0020 process** (4-phase library SDLC + 8-dimension taxonomy + shared `_ctl/lib.sh` phase-gate +
  project-go hooks + `errors` reference impl): libs 25b58c4, eden 4e46682.
- ✅ **Devcontainer is THE substrate** (.devcontainer 52a1228, eden pointer bumped): base image carries the
  full gate toolchain + bun + go1.26.4; new `ctl.sh up/exec/shell/down` lifecycle (repo→/workspace, docker
  socket); post-create installs the pinned harnesses + hnslint. docker-out-of-docker verified. The spawned
  agent pods will dogfood this same image family (Mateo, 2026-06-13). Publish CI's disk-OOM fixed.
- ✅ **Harness versions pinned + gated** (ADR-0021; eden 98565de, libs 4f29a4e): `harnesses/versions.env`
  is the one source of truth; post-create installs exact versions; `harness-conformance` re-proves a pin
  against the real adapter; `harness-upgrade-check` opens the bump PR. (omp 15.10.0→15.12.4 already proved
  conformant — the gate works.)

- ✅ **agentsession is DONE — `phase-gate all` GREEN** (libs 656e615, eden pointer bumped): the omp adapter +
  the full ADR-0020 8-dimension taxonomy (property/leak/lifecycle/load/canary/bench across root+claudeadapter+
  ompadapter), gosec-clean, contract frozen, .apibaseline+.benchbaseline recorded. Verified in-container
  against the REAL claude + omp harnesses. This is the TEMPLATE for the per-lib sweep below.
- ✅ **Shared phase-gate engine HARDENED** (libs 983047d): the first full `phase-gate all` on a multi-tool
  substrate lib surfaced + I fixed several latent gate bugs (the process workflow had only run a leaf lib's
  implementation gate): cohesion over-reach on idiomatic Config/Adapter; the integration tool-check IFS
  word-split (broke every multi-tool substrate lib); bench-guard now gates allocs/bytes tight + wall-time
  loose (env noise); cover-floor excludes stub-harness binaries, runs tag-aware, and uses -coverpkg + a
  union-correct extraction so the conformance two-binding suite's coverage of the root contract counts
  (root 80.2%); 2x SC2015. **These unblock the per-lib sweep for every other substrate lib.**

- ✅ **Retroactive QA sweep Batch 1 DONE** (libs e45701d; eden contract freezes + pointer bump): 6 libs
  (configuration, dependencies, observability, secrets, testing, gitrepository) swept to `phase-gate all`
  GREEN via a 6-agent Opus workflow, then **independently re-verified by me** with a corrected gate. The
  re-verify caught that the agents' green leaned on EPHEMERAL gremlins workarounds (image pinned gremlins
  v0.5.0 lacks `unleash --exclude-files`) → fixed 3 more central gate bugs: gremlins pin → 0.6.0
  (.devcontainer 5f6d33f), a real cmd_lint blind-gate (golangci/vet failures slipping through
  `maintainability` — reproduced + fixed + verified), bench-guard wall-time → advisory (gate hard only on
  deterministic allocs/bytes). Agents also fixed real prod bugs (observability `Exporter` cohesion break +
  G115; gitrepository G204/G306). All 6 re-verified GREEN with the fixed gate.

- ✅ **workspaceprovider DONE — phase-gate all GREEN** (libs 0d3cb95; eden contract freeze + pointer): the
  full taxonomy over the REAL docker + k3d/kind substrate (all reaped, CountOwned==0). The real-substrate
  test caught a genuine prod bug — VehicleFile credential injection was silently broken (tmpfs can't take a
  CopyToContainer write) → rerouted via exec+stdin, proven on real docker — plus 3 gosec G115 hardenings.
  Engine: cohesion exemption generalized to suffix families (...Config/Adapter/Options, libs 09c8cf9).

- ✅ **orchestrator DONE — ALL 11 Go libs are ADR-0020 phase-gate-all GREEN** (libs d5d11c3; eden contract
  freeze + pointer). orchestrator's port-based reconciler swept (real-pod-over-real-harness is Milestone B,
  correctly not fabricated; production .go untouched). Verification surfaced 2 reachable+UNFIXABLE
  docker/docker CVEs (GO-2026-4887 AuthZ-plugin-bypass, GO-2026-4883 plugin-privilege off-by-one; Fixed:
  N/A) affecting the docker-using libs — NOT exploitable in Eden's controlled docker-client provisioning
  (no authz/legacy plugins). The vuln gate is now DETERMINISTIC with a documented accepted-risk allowlist
  (libs a36ce85); re-review/drop when docker/docker ships a fix or Eden adopts moby/moby/v2. **TASK #4
  (retroactive QA sweep) COMPLETE. → Mateo to ratify the CVE acceptance.**

- ✅ **Milestone B architecture RATIFIED — ADR-0022** (after the IOTEA-archive study, 4 Opus research agents):
  (1) secrets→Vault NOW, ephemeral per-session role, **REAL Vault locally** (official image, no custom build,
  not -dev); (2) deploy two-axis compose-local/helm-prod, supporting stack (NATS+Postgres+Vault) out-of-band,
  one typed ServiceSpec→both; (3) http-api = stateless NATS→SSE bridge + REST-POST control (edenhttp lib,
  IOTEA 6-stage pipeline); (4) **FAT provider** — workspaceprovider absorbs supervision + lifecycle-event-
  normalization + the Entrypoint/workload-pod capability (a contract revision; resolves OD-15 opt-a),
  orchestrator thins. IOTEA cloned at /Users/mateo/iotea-archive.

- ✅ **B1: secrets Vault backend DONE — phase-gate all GREEN** (libs 2431ec4; eden pointer bumped): a new
  `secrets/vaultadapter` resolves `vault://<mount>/<path>#<key>` from a REAL HashiCorp Vault KV v2 mount,
  behind the EXISTING Mediator/Provider port (NO contract revision; secrets.md stays Frozen, .apibaseline
  additive). Dual-mode bootstrap (ADR-0022 #1): ModeUserpass (local) / ModeTokenFile (prod K8s-SA sidecar),
  chosen by Config not a caller fork. The REAL-Vault integration lane boots the official hashicorp/vault
  container (server mode + one-shot init/unseal, NOT -dev) over docker-out-of-docker and round-trips a canary
  byte-for-byte, no leak; 403→Denied/404→NotFound typed errors proven against real Vault. secrets is now a
  substrate lib (leaf=false, floor=70). **Independently re-verified by me** — the agent's first green was
  actually RED on vuln (go-jose v4.1.1 → bumped to v4.1.4, clears GO-2026-4945) + cover-floor (raised to
  87.9%); both fixed and the full gate re-run GREEN in-container before commit. Also retired the last
  `.dev-secrets` reference (ompadapter live key → env-only, libs 2431ec4), completing the .env migration.
- ✅ **B2: workspaceprovider FAT provider + Entrypoint DONE — phase-gate all GREEN** (libs f422eaa; eden
  pointer + contract re-freeze): an ADDITIVE contract revision (ADR-0022 #4, no break — apidiff additive-only)
  extending the frozen workspaceprovider. §7 Q15 supervision — new `Supervisor` port (Supervise/Supervised/
  Reconcile) on `*Provisioner`, a label-filtered docker-events / k8s pod-watch normalized into ONE `Event`
  space (reusing State/Condition), reconcile-from-reality (list-by-label re-adoption after a fresh-Provider
  restart), optional `Watcher` adapter seam + `CapSupervise`; Supervised Status read from the LIVE substrate
  (what the thin orchestrator will Probe). §7 Q16 Entrypoint/workload-pod (closes OD-15→RD-15 opt-a) — one
  new `WorkspaceSpec.Entrypoint []string`: the container's MAIN process IS the workload (PID-1) on docker AND
  k8s; empty = Q14 exec-into-hold verbatim (existing consumers unaffected); `ConditionOOMKilled` now surfaces
  natively (`CapWorkloadPod`). **Independently re-verified by me** (the agent ended mid-gate without a clean
  report): ran the full `phase-gate all` myself in-container GREEN on real docker + k3d (the OOM proof is
  no-skip on docker; honest-skip on k3d where the node doesn't enforce the cgroup), reviewed the additive
  `.apibaseline` + §7 Q15/Q16 + RD-15, and completed the contract re-freeze. Watch goroutine leak-free.
- ✅ **B3: PID-1 agent-runtime sidecar + NATS/JetStream bus DONE — phase-gate all GREEN** (libs 3399d04; new
  `apps/agent-runtime` + frozen `agentruntime.md` contract; eden pointer): a NEW lib `libs/go/agentruntime`
  runs the harness as the container's PID-1 — pure `New(Config, Deps)` over consumer ports (Bus/Observer/Clock);
  the Run loop is a graceful-shutdown state machine (Open→pump agentsession events→publish sequenced to
  JetStream `agent.<id>.events`→subscribe `agent.<id>.control` prompt/steer/abort/stop/kill→`agent.<id>.health`
  heartbeats→drain→OTel flush→typed reason); active-agent registry backs kill; `/live`+`/health/{id}` probes.
  Typed 3-subject protocol, OTel carrier on every msg, JetStream MsgId==Seq (gap-free replay — the surface B5
  consumes). `natsbus` is the only nats.go import; `otelobserver` bridges observability. `apps/agent-runtime`
  is the thin PID-1 main (the workspaceprovider Entrypoint runs it). **Independently re-verified by me** — the
  agent reported green but had left a workspace-breaking go.mod conflict (module-level `replace` blocks in the
  new go.mods clashing with the go.work-centralized replaces); I removed them (matching the agentgateway/secrets
  pattern), then ran `phase-gate all` myself GREEN on REAL nats-server+JetStream (embedded AND a real container,
  never mocked) + a real agentsession subprocess, race+leak clean, and smoked the app (/live 200, graceful
  exit-0 on SIGTERM).
- ✅ **B4: thin orchestrator over REAL pods DONE — phase-gate all GREEN** (libs c695a9a; eden pointer + contract
  doc): binds the Milestone-B substrate behind the EXISTING orchestrator ports (ADR-0022 #4, no surface break —
  `.apibaseline` unchanged). Real Probe via the B2 `Supervisor.Supervised` (the HARD lifecycle, not the
  in-memory liveTable/heartbeats); real **Postgres DesiredStore** (pgx) so desired survives node recycle; real
  Pool over real workspaceprovider (docker+k3d) + Postgres + NATS, Stop/Kill records durable intent FIRST then
  publishes to `agent.<id>.control` (OTel on every msg); provisions an Entrypoint workload-pod (agent-runtime
  PID-1). Production: additive `SandboxSpec.Entrypoint` + `driveResume` now re-provisions a gone workspace on
  re-adopt (idempotent on Name). **Independently re-verified by me** — reviewed the flagged `driveResume`
  reconcile change (correct survive-recycle) + the additive field, confirmed `.apibaseline` unchanged, ran
  `phase-gate all` GREEN myself on REAL docker(N=3)+k3d(N=2)+Postgres+NATS (spawn→recycle→suspend→resume→
  stop→kill, load N=5 -race, CountOwned==0, weaken-to-confirm non-vacuous), and confirmed all apps still build.
  Real adapters live in the integration/load lane so the orchestrator core stays pgx/nats-free.
  - ⚠️ **Carried forward (flagged, not blocking):** (a) **B8 handoff** — the gate uses a busybox Entrypoint;
    the full demo still needs the real agent-runtime CONTAINER IMAGE built + the in-pod sidecar consuming the
    `agent.<id>.control` verbs the orchestrator now publishes + a token-gated real-claude/omp-in-pod arm.
    (b) `kubernetesadapter` namespace derivation truncates to 63 chars dropping the per-agent discriminator on
    long names — latent collision risk; a hash-suffix is the future hardening (prod ownership prefixes are short).
- ✅ **B5: edenhttp + stateless NATS→SSE gateway DONE — phase-gate all GREEN** (libs 73014f4; agentgateway
  reworked + frozen `edenhttp.md`; eden pointer): NEW lib `libs/go/edenhttp` — the IOTEA 6-stage pipeline
  (parse→validate→authorize→execute→respond→action) + uniform `{data,errors,kind}` envelope + an SSE writer +
  the `natssse` JetStream→SSE bridge (replay by Seq, reconnect gap-free) + a stdlib-only HMAC-SHA256 dev-JWT
  verifier (alg-pinned, constant-time) + the `namespace:action` grant grammar. `apps/agentgateway` reworked:
  the production path is now the **stateless** bridge (`internal/stateless` + `internal/natscontrol`); the
  in-process Pool dev-serve stays for fakes. **Independently re-verified by me** — confirmed the gosec-G101
  nolints annotate only vault REFERENCES + a fake dev token (not real secrets), all apps build, edenhttp
  `phase-gate all` GREEN, and ran the agentgateway real-NATS end-to-end myself: 6/6 PASS (SSE streams by-Seq
  with JWT, reconnect resumes gap-free, 401 unauth, 403 under-granted, control publishes to NATS, verb routes).
  - 🎯 **UI handoff (the surface B7 calls; `Authorization: Bearer <dev-JWT>` on all but `/healthz`):**
    `GET /sessions/{id}/events` → SSE (`event:`=agentsession EventKind, `id:`=Seq, `data:`=EventEnvelope JSON;
    reconnect via `Last-Event-ID`/`?from-seq`; grant `sessions:read`). `POST /sessions/{id}/control` body
    `{"verb":"prompt|steer|abort|stop|kill","text":"…"}` (or `POST /sessions/{id}/{verb}` `{"text":"…"}`;
    grant `sessions:control`). Uniform `{data,errors,kind}`; dev JWT signed with `EDEN_GATEWAY_JWT_SECRET`.

- ✅ **B8: `deploy local` + the LIVE REAL-AGENT demo DONE — verified end-to-end + committed** (eden 30038f0,
  after my secret-hygiene re-verification): the ONE-COMMAND path is `bash deploy/ctl.sh demo` → open `http://127.0.0.1:5173/chat`
  → chat a REAL claude agent whose credential resolves through the REAL local Vault (seeded from
  `.env.development`). VERIFIED MYSELF in-container: a real `claude` turn streams the full taxonomy
  (session-state→message-start→text-delta→usage→message-end→**result "pong"** with the live ledger
  costMicros) to the B7 UI THROUGH the vite same-origin proxy; secret-safe (no value in any log/committed
  file; `kv get` returns a 108-byte value WITHOUT printing it). **Chosen path (b) single-process** (ADR-0022
  #2 dev-local convenience): a new `apps/agentgateway/cmd/agentgateway-live` + `internal/liveserve` wires the
  full `internal/gateway` over a REAL `agentsession.Pool` (claude/omp adapters, in-process subprocess — no
  pod) + the secrets Mediator over the REAL `hashicorp/vault` (ModeUserpass, seeded). The DISTRIBUTED path
  (a) is scaffolded: `deploy/plane/{local=compose,production=helm}`, ONE typed Go `ServiceSpec`
  (`deploy/servicespec`) rendering to BOTH a compose overlay AND a Helm chart (image-tag-as-environment-
  contract), the supporting-stack compose (Vault server-mode+NATS/JetStream+Postgres, out-of-band), a
  secret-safe Vault-seed step (`deploy/plane/local/vault-seed.sh`, NEVER echoes a value), and Dockerfiles for
  agent-runtime (dogfoods the `.devcontainer` base) + gateway.
  - ⚠️ **Real bug found+fixed (the B7 surfaceGap / B4 b8Handoff edge):** `internal/gateway`'s
    `handleCreateSession`/`handleControl` opened/prompted the live session with the REQUEST context — fine for
    the synchronous FAKE harness (it emits its whole turn before the POST returns) but it tore down a REAL
    async claude mid-turn ("harness stream ended without a terminal event") the instant the 201 was written.
    Fixed: the session + its turns run under `context.WithoutCancel` (lifecycle owned by the registry +
    Serve shutdown, not the request). The fake-harness gateway/devserve suites still pass.
  - 🔲 **REMAINING for full path (a):** build+load the agent-runtime/gateway CONTAINER IMAGES and run the
    distributed compose (orchestrator spawns the PID-1 pod, gateway is the stateless NATS→SSE bridge); a k3d
    `helm install` of the rendered chart (the chart renders; a full apply is the follow-up). The record-plane
    ledger (`GET /sessions/{id}`) is the orchestratortest in-memory plane and does not mirror the live SSE
    ledger — cosmetic for the demo (the UI renders the live `result`), real for path (a). omp is NOT installed
    in the current devcontainer image, so the live arm was verified on **claude** only; the omp adapter is
    wired and seeded (openrouter-api-key in Vault) but unverified live until the image carries omp.

🎉 **DEMO-CRITICAL PATH COMPLETE — the live UI chats a REAL agent.** ✅ B1 · ✅ B2 · ✅ B3 · ✅ B4 · ✅ B5 ·
✅ B7 (chat UI) · ✅ B8 (deploy local + live demo). Seven Milestone-B pieces shipped overnight 2026-06-13→14,
EACH independently re-verified by me before commit (every build agent left ≥1 real defect I caught: B2 ended
mid-gate, B3 a workspace-breaking go.mod replace conflict, B5 gosec-nolint vetting, B8 a real async-harness
context bug). Run it: `bash deploy/ctl.sh demo` → http://127.0.0.1:5173/chat.

✅ **FINAL REVIEW DONE (Opus, 2026-06-14)** — verdict: **SAFE to hand Mateo.** secretAudit **PASS** (no real
credential in any committed file/log/persisted surface — gitignore coverage live-verified, vault-seed.sh
`set +x` names-only, vaultadapter mints un-printable secrets + reference-only typed errors, servicespec never
inlines a secret), cohesion + HNS-1 **PASS** (zero `helios`, no duplicate contract types), **zero CRITICAL**.
Applied the two cheap cleanups it flagged: pinned `nats:latest`→`nats:2.14.2` (matches the libs' embedded
server), and this note: **the demo gateway (path b / `agentgateway-live`) is INTENTIONALLY auth-free +
loopback-only** (127.0.0.1) — a deliberate dev convenience, not an oversight; the PRODUCTION stateless gateway
(path a) is behind the edenhttp dev-JWT + grants.

REMAINING (post-demo, NOT demo-blocking — the review's path-(a) backlog, top two MUST NOT be forgotten):
- 🔺 **HIGH (path-a blocker #1):** the B7 frontend posts `{command:…}` no-auth to `/control`; the production
  stateless gateway expects `{verb:…}` behind the JWT. The UI works against the live/dev gateway but is
  silently INCOMPATIBLE with the stateless gateway → unify the control DTO (`verb`) + have the frontend mint/
  attach a dev-JWT + add a contract test driving the SAME client against the stateless gateway.
- 🔺 **HIGH (path-a #2):** `agentruntime/runtime.go` logs+continues on a failed events `PublishEvent` → that Seq
  never reaches JetStream, so the gateway's "gap-free replay" can gap. Retry/backoff or fail the run on a
  persistent events-publish failure (heartbeat-publish failures stay tolerable).
- **B6** git-backed `agent-configs/` + strict-by-default sandbox (config-as-code + per-tool grants) — hardening.
- **Full distributed path (a)** — build/load the agent-runtime + gateway CONTAINER IMAGES + run the
  orchestrator-spawns-PID-1-pod / stateless-NATS→SSE-gateway compose + a k3d `helm install` (the chart renders;
  apply is the follow-up). The live demo uses single-process path (b); the distributed path is scaffolded.
  The record-plane ledger (`GET /sessions/{id}`) doesn't mirror the live SSE ledger (cosmetic for the demo).
- **omp live-in-pod** unverified (omp not in the current devcontainer image; adapter wired + key seeded).
- **Lower:** dev-JWT `exp==0` never expires (edenhttp — dev-only); SSE reader has no max-reconnect cap;
  **Codex** PARKED (no OpenAI key); the k8s namespace 63-char truncation hardening (RD-15 note).

MATEO'S CLOSING DIRECTIVE: ensure all committed + pushed, then **one full review of everything done** = a
final cleanup + improvement pass. Drive autonomously to that clean, reviewed, pushed end state; call Mateo
only if stuck. NEW standing constraints (2026-06-13): work ONLY in the devcontainer (never the host);
pinned harness versions; agent pods dogfood the devcontainer images.

## ▶ POST-DEMO PROGRAM (2026-06-14) — application-templates + the UI foundation (single orchestrator)

After the live demo, Mateo opened two new tracks and **consolidated to one orchestrator** (the parallel
UI/TypeScript agent handed off — handoff doc `docs/attic/handoff-ui-libs.md` (attic'd 2026-07-06), eden 455b1fd).
Strategy (Mateo agreed): **DEPTH-FIRST on ONE working vertical** (http-gateway backend ⇄ OpenAPI ⇄ a real
UI) before scaling breadth; **integration seam = OpenAPI** (the backend emits, the UI generates its client).

- ✅ **application-templates repo created** (4th submodule sibling to `libs`) — production-grade Eden app
  templates so Eden builds standard SaaS backends and builds itself. ADR-0023 + doc-16 (eden bd59599):
  sqlc/pgx, OpenAPI-first, **5-files-per-route**, two codegen axes (persistence + clients), `.claude`
  enforcement at both repo and per-template level.
- ✅ **http-gateway template — Wave 0 + Wave 1 DONE, phase-gate all GREEN on REAL Postgres** (application-
  templates 8e3da50 + bfd46e4; eden pointer ae616eb + RD-17 OpenAPI go-first). A COMPLETE running backend:
  `cmd/gateway` composition root, `internal/api/v1/resource/{create,get,list,update,removal}` (5-file CRUD),
  sqlc/pgx persistence, `contract/openapi.yaml` go-first-emit, oapi-codegen Go client. `TestIntegration_
  ResourceCRUD` drives full CRUD through the generated client against real `postgres:16-alpine` + 401/403
  authz, weaken-to-confirm, 0 orphans. Independently re-verified (GATE_EXIT=0).
- ✅ **objectstorage gated lib DONE — phase-gate all GREEN on REAL MinIO** (libs b2f7445): `ObjectStore`
  port (Put/Get/Delete/Presign/List — exactly 5), MinIO adapter, typed errors. Real-substrate finding: an
  S3 presigned URL embeds the access-key ID (public) but never the secret.
- ✅ **UI Foundation Wave A DONE — `phase-gate all` GREEN, independently re-verified** (libs 517ac0a; eden
  pointer bumped). ADR-0024 (TS/Svelte library pipeline, eden 2dd6d0e) + research/05 (the design math).
  `libs/typescript/_ctl/lib.sh` mirrors the Go ADR-0020 pipeline (`bun x` tooling, istanbul coverage, apidiff
  cardinal-sin gate, HNS-1 name lint) + the **ninth dimension: design-correctness** — mechanical UI-math QA.
  `@eden/scale` (modular-scale generator, 16 tests 96% cov) + `@eden/theme` (token engine: OKLCH color
  science, WCAG+APCA contrast gate, ramp/typography/spacing/density/motion, DTCG export, C21 seed,
  `generateTheme`; 86 tests incl. **20 design-correctness assertions** bound to research/05; 99.71% cov).
  UI-math thoroughness PROVEN to Mateo's bar: contrast weaken-to-confirm (a forced 2.224:1 pair fails the
  design verb non-vacuously) + a self-checking contrast audit (a lying stored audit fails the gate).
  - ✅ **RESOLVED (founder ruling 2026-06-14, RD-18):** `OD-17-c21` + `OD-17-type-ratio` + `OD-17-density-default`.
    Density — not heading-drama — is the user-facing richness axis. `@eden/theme` now ships a **three-step
    `DensityMode`** (`relaxed`/`standard`/`dense`; middle recommended; `dense`=expert, "directly applicable to
    Eden itself") resolving to engine tiers consistent with `DEFAULT_DENSITY`. The type ratio stays **1.20**
    (re-derived sizes, no hand-set 48; the 5 colors + 3 fonts stay immutable seeds). (libs b7ff809.)
  - ✅ **RESOLVED:** the touch-floor — `generateTheme`'s `targetContext` now **defaults to `touch` (44px AAA)**;
    the decoupled hit target clamps to 44 at any density (visual box still shrinks), proven by a
    design-correctness weaken-to-confirm (pointer drops the densest below 44). 24 design assertions, gate GREEN.

## ⏸ (superseded) LOOP PAUSED — backend phase COMPLETE; two items genuinely require Mateo (2026-06-13)

The autonomous loop drove the **entire backend to done, verified, and pushed**, then paused — it has
exhausted the unambiguous work. The two remaining items both require Mateo and cannot be done
autonomously without overriding his explicit wishes:

1. **The visual chat UI direction** (the keystone). I asked twice (terminal + mobile push + a message
   with three concrete directions: Claude-faithful / observability-dense / session-fleet) and committed
   to NOT building it blind — it is the feature he wants to shape (look/feel/UX, Eden identity C21). The
   backend it needs is 100% ready and RUNNABLE: `GOWORK=/Users/mateo/helios/go.work go run
   ./libs/../apps/agentgateway/cmd/agentgateway-dev` (default 127.0.0.1:8080) serves the full REST + SSE
   surface over fakes — no real auth needed. When Mateo gives direction, build the SvelteKit chat UI in
   apps/frontend against that gateway, then Playwright forced-CRUD E2E.
2. **The real `claude setup-token`** (REQ-0021). The real claude-code authenticated run is wired
   (libs/go/agentsession/claudeadapter) but GATED — it needs Mateo to run `claude setup-token` once. I
   must not mint it or touch ~/.claude.

DONE this run (all on origin/main; eden pushed): 4 backend libs (workspaceprovider ed65211, gitrepository
f3cb2c1, agentsession f629479, orchestrator ee2b37f), agentgateway HTTP/SSE service + dev-serve (eden
29d97d7), the pre-commit-hook workspace fix (191e64b), and the doc-13 branch-name hook + merge-agent role
(b3d8de8). Each lib built TDD under enforcement by an Opus workflow, then INDEPENDENTLY re-verified by the
manager loop (full gate + real integration + my own weaken-to-confirm-non-vacuity); I caught + fixed real
issues the subagents missed (two vacuous conformance guards, a credential-leak blind spot, an over-reported
contract divergence, HNS-1 abbreviations, the hook gap). Working tree clean; both repos synced; vite preview
:4173 left running for Mateo; render toolchain at /tmp/eden-render (consolidation deferred — not safe while
vite is live). TO RESUME: reply with chat-UI direction (and/or run `claude setup-token`), or re-fire /loop.

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
- **NEXT: Wave 3B cont.** — agentgateway backend service (IN PROGRESS) → SvelteKit chat UI → Playwright E2E
  (+ doc-13 branch hook + merge agents).
  - **agentgateway (backend service) sub-wave ✅ DONE + COMMITTED + PUSHED** (eden repo; an APP, no submodule
    pointer change). Go HTTP/SSE backend-for-frontend in apps/agentgateway (module github.com/gophersys/eden/
    apps/agentgateway) wrapping orchestrator.Manager + agentsession.Pool: REST POST/GET /sessions (+list/get/
    stop/resume/control/transcript/healthz) + per-session SSE /sessions/{id}/events (event:<kind> id:<seq>
    data:<json>, Last-Event-ID/?from-seq replay = same mechanism, per-session fan-out off the agentsession
    Session, prompt-flush <1s, clean terminal end). Pure New(config,deps); credentials opaque secrets.Reference
    only, NO .Resolve/.Use path, no wire DTO has a credential field, 5xx fixed generic body. Built by workflow
    wa97yv5b1 (Opus, ~33min). Verify agent verdict PASS (all 8 properties true; 5 weakens — replay/fan-out/
    ordering/control/credential — each broke the right test, the credential weaken made the canary scanner fire).
    I VERIFIED MYSELF: full gate green (gofumpt, golangci 0 both alone w/ libs/.golangci.yml, vet both, race
    both), integration 8/8 race-clean. FIXED the HNS-1 abbreviations the forbidigo token-list missed:
    TemplateVer→TemplateVersion, the *Vw view-DTO suffix→*View (stateView/messageView/etc.) — gate still green.
    The gateway HANDLER itself is fully wired + httptest-proven, so REQ-0020..0024 are covered.
  - **agentgateway DEV-SERVE ✅ DONE** (workflow w3jufpfyt, single Opus agent): apps/agentgateway/internal/
    devserve/ (BuildDevGateway wires orchestratortest.Manager + a REAL agentsession.Pool over the agentsessiontest
    scripted harness + secretstest fake setup-token + a real Transcript + fixed Clock) and cmd/agentgateway-dev/
    main.go (a real net.Listener + graceful shutdown). `GOWORK=… go run ./cmd/agentgateway-dev` (default
    127.0.0.1:8080) serves the FULL gateway over fakes — no real setup-token. Production cmd/agentgateway is
    UNTOUCHED + imports NO test fakes (verified). Smoke test TestSmokeDevGatewayHappyPath green. I VERIFIED
    MYSELF: full gate green, and I ACTUALLY RAN the binary (127.0.0.1:18099): /healthz 200, POST /sessions →
    agent-1, GET /sessions lists it, SSE id:1..14 full taxonomy (session-state/message-start/thinking/text×2/
    tool-start/tool-end/usage/message-end/result), graceful shutdown. OPEN ITEMS for the frontend sub-wave
    (recorded, not blockers): dev CORS (likely moot if the SvelteKit dev server Vite-proxies the gateway);
    template-name discovery (dev seeds implementer-go@1.0.0; exposed via DefaultCreateTemplate() + startup log);
    a 0.0.0.0 bind option for devcontainers (already supported via EDEN_DEV_ADDRESS). Real-composition-root
    (production main over real Pools + claudeadapter + listener) still needs the kernel wiring + Mateo's
    setup-token. No stragglers.
  - **agentgateway (workflow ref)** — task wa97yv5b1 / run
    wf_04649f8c-759, Opus impl→adversarial-verify; does NOT commit). A Go HTTP/SSE backend-for-frontend in
    apps/agentgateway (eden repo, NOT the submodule; module github.com/gophersys/eden/apps/agentgateway) wrapping
    orchestrator.Manager + agentsession.Pool: REST spawn/list/get/stop/resume + transcript read, and per-session
    SSE event streams honoring Last-Event-ID/?from-seq (the REQ-0023 replay = same mechanism), individually-typed
    events (REQ-0024), per-session fan-out (REQ-0022), credentials resolved server-side and NEVER to the browser
    (REQ-0021). Tested via httptest + the agentsessiontest fake harness end-to-end + orchestratortest fakes;
    integration -race with concurrent SSE clients + reconnect-replay + fan-out-isolation + credential-canary
    checks, leak-free. On completion VERIFY MYSELF (gate + integration -race + weaken replay/fan-out/seq/control/
    credential), then commit + push (eden repo; no submodule pointer change — it is an app, not a lib). Do NOT run
    conflicting work in apps/agentgateway while it runs.
  - **doc-13 git tooling ✅ DONE** (while awaiting Mateo's chat-UI direction): (1) the branch-name pre-push
    hook — `hook_check_branch_name` in `.githooks/lib/common.sh`, wired into `.githooks/pre-push`, validating
    the doc-13 §2 grammar `<class>/<slug>[/run-<id>]`; BLOCKS off-grammar AGENT branches (/run-<id> suffix),
    only WARNS for off-grammar human branches (so `init/seed` is never blocked — §9 Q3 default). Regression-
    tested by `.githooks/lib/branchname_test.sh` (16 cases, shellcheck-clean; the test caught a real grammar
    bug — release/eden-v0.2.0 needs dots in the slug — now fixed). (2) the `merge-agent` role —
    `.claude/agents/merge-agent.md` (Opus): clean worktree → full class gate → fix-mechanical-to-green-within-
    budget → ff-only merge through gates → remove worktree, escalate-never-decide on frozen contracts/approved
    artifacts/human-ruling gates/real bugs/budget. doc-13 §2/§6 now point to the landed artifacts.
  - **NATURAL CHECKPOINT after agentgateway:** surface to Mateo before the VISUAL SvelteKit chat UI — the chat
    surface is the keystone feature he wants to see/shape (visual identity C21, UX); his eyes matter most there.
    The backend service is un-ambiguous (REQ-0020..0024) so it proceeds autonomously; the frontend should get his
    input on direction first.
  - **orchestrator v0 sub-wave ✅ DONE + COMMITTED + PUSHED** (libs ee2b37f on origin/main; eden pointer bumped).
    The S2 desired-vs-actual reconcile loop over agentsession + workspaceprovider: Manager (Spawn/Get/List/Stop/
    Resume, exactly 5 methods) on plain serializable RECORDS (Handle + opaque SessionRef, no live Session — the
    multi-node seam), template fold (ceiling+floor, tightening-only), reconcile spine (Spawn→Pending returns
    immediately; converge Provisioning→Running; Stop drains+Releases, Teardown is the SOLE pod-teardown via
    Close-then-Teardown; Resume re-attaches), one admission authority (MaxConcurrent per (Tenant,Template)
    atomic BEFORE provisioning), budget watch, observability on the Telemetry seam. Credentials threaded into
    agentsession.Spec.Credential out-of-band, never resolved by orchestrator, never in any record/Event/store/
    log/error. Conformance (14 cases) over the REAL agentsession.Pool + REAL workspaceprovider.Provisioner;
    integration proves 300-agent convergence + 120-agent Spawn/Stop/Resume churn + 200-way admission burst
    (exactly the ceiling admitted, refusals provision nothing) — all race-clean + leak-free. Built by workflow
    wq8sbwius (Opus, ~46min). Its verify agent caught the impl agent OVER-REPORTING (falsely claimed zero
    contract divergence) and surfaced two findings: (RESIDUAL-1) the Agent record silently gained Desired+Cluster
    fields beyond frozen §4 → recorded as the Q11 ratify-pending amendment (additive, sound design); (RESIDUAL-2)
    the credential no-leak GUARD was blind to transient-field leaks (scanned only the final record). I VERIFIED
    MYSELF: full gate green (gofumpt, golangci 0 both alone, hnslint, vet both, race both), race-clean. FIXED
    RESIDUAL-2: the fake DesiredStore now retains the full Put history and AssertNoSecretInRecord scans every
    version; added a non-vacuous regression test (TestAssertNoSecretInRecord_CatchesTransientLeak) proving a
    leak into an overwritten transient field is now caught. RESIDUAL-1 accepted as Q11 (the design is sound;
    the process violation is corrected by the recorded amendment). No stragglers.
  - **orchestrator v0 sub-wave (workflow ref)** — task wq8sbwius / run wf_054229a1-193,
    Opus impl→adversarial-verify; does NOT commit). The S2 desired-vs-actual reconcile loop over agentsession +
    workspaceprovider: template resolution (fold AgentTemplate ceiling + spawn floor into agentsession.Spec +
    workspaceprovider.WorkspaceSpec), reconcile spine (Spawn→Pending returns immediately, loop provisions+opens
    +drives; Stop drains+Releases the pod which is the SOLE teardown path; Resume re-attaches; Get/List read
    RECORDS not handles = the multi-node seam), MaxConcurrent admission BEFORE provisioning, budget watch,
    observability on PlaneAgent. Credentials: thread the opaque secrets.Reference into agentsession.Spec.Credential,
    NEVER resolve it. Real integration drives the REAL agentsession (fake harness) + workspaceprovider ports,
    race-clean concurrent reconcile, leak-free. On completion VERIFY MYSELF (gate + integration -race + weaken
    admission-before-provision / exactly-once-release / budget-stop / returns-immediately / credential-leak), then
    commit + push + bump eden pointer. Do NOT run conflicting work in libs/go/orchestrator while it runs.
  - **BUILD-ORDER CORRECTION (2026-06-13):** the loop's stated order (orchestrator → agent-session) is
    INFEASIBLE — orchestrator imports the agentsession package extensively (Spec×8, Session×4, Factory×3,
    TokenLedger, State, Budget, Event, …) and cannot compile without it. So the dependency-correct order is
    **agentsession (F4 library) FIRST → orchestrator (consumes agentsession + workspaceprovider) → chat UI
    (consumes the agentsession Event stream + orchestrator) → Playwright E2E.** agentsession is also the
    keystone the chat UI needs (the server-triggered Event stream). Building it first.
  - **agentsession sub-wave ✅ DONE + COMMITTED + PUSHED** (libs f629479 on origin/main; eden pointer bumped).
    The keystone F4 agent-abstraction: one Session primitive (Events/Control/Resolve/Close), the full 15-kind
    normalized Event taxonomy with monotonic Seq==transcript-offset, replay-then-tail fan-out (Last-Event-ID
    reconnect / FromSeq(0) replay / old-Run reload / engine fold = ONE race-clean mechanism; slow-subscriber
    demote→catch-up, gap-free), tool grants + host-tool + first-decision-wins permission round-trip, TokenLedger
    fold (integer micro-cost, no float drift), single-authority budget abort, and the setup-token credential
    seam (opaque secrets.Reference → server-side Secret.Use → one scrubbed child-env entry, never argv/Spec/
    Event/log/error/transcript). Deterministic fake harness end-to-end + real claude-code adapter WIRED but
    GATED (stub-binary subprocess exercises the real spawn/scan/Close ladder; live auth gated on Mateo's
    setup-token, never minted, ~/.claude untouched). Built by workflow w1zqzprbj (Opus, ~64min); its verify
    agent ran 8 weaken/revert non-vacuity proofs. I VERIFIED MYSELF: full gate green (gofumpt, golangci 0
    default+integration alone, hnslint, vet both, race both), race-clean 24-tailer fan-out, leak-free; my OWN
    Seq+1 weaken broke SeqMonotonic + ReplayGapFree (reverted). FIXED the one honest residual the verify agent
    flagged — the SilentBadToken conformance case was VACUOUS (used FailSpawnWith, bypassing the pump); added a
    fake non-readying mode (SpawnNonReadying) so it drives the pump's genuine no-ready→AuthError synthesis,
    proven non-vacuous by my own weaken. Additive-to-contract notes (non-breaking, in the commit msg):
    ConfigError/RouteError beyond the 5 named errors; Event.Terminal()→IsTerminal() (Go field/method collision).
    No stragglers (let-it-finish discipline held again).
  - **agentsession sub-wave (workflow ref)** — task w1zqzprbj / run wf_16d84369-a55,
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
