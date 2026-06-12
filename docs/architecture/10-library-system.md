# 10 — Library System

> Status: Draft · 2026-06-12 · Canonical home for: library-system principles, the
> environment≠platform axes, folder architecture, the pattern catalogue, HNS-1 naming,
> per-ecosystem structure, the app stack, the dev→release→adopt lifecycle, API discipline, and
> the library manifest.
> Provenance: migrated from `/LIBRARY-SYSTEM.md` + `/LIBRARIES.md` (2026-06-03, synthesized from
> a 14-agent research swarm; originals preserved verbatim in `docs/attic/`). Updated for the Eden
> rename (ADR-0002), the Go 1.26 floor (ADR-0003), the Svelte re-platform (ADR-0004/0005), and
> the ADR-0009 rulings. **§1–§9 keep the source document's section numbers** so existing
> citations of the form "10 §N" resolve unchanged.

## 1. Principles

1. **Self-hosting.** Apps built *with* Eden consume the same first-principles libraries Eden
   itself is built on (= P11).
2. **Language-first.** Libraries are partitioned by ecosystem (`libs/<ecosystem>/…`) because
   packaging, versioning, publishing, dependency resolution, and the local↔remote dev swap are all
   language-bound. A **domain** (cloud-backend, embedded-rtos, native-ui) is a *recipe* composing
   patterns — never a directory tier.
3. **Dogfooded consumption.** The monorepo's own apps consume libraries from their **published
   remote** versions, never from source — except during active library development, when a local
   override points the app at in-repo source. **The override must never reach `main`.**
4. **Full naming, no abbreviations** (= P12, enforced via §5's lint table).
5. **Hexagonal everywhere** (= P1) — the constructor spine and its purity rule live once in §4.
6. **Cross-language coherence comes from names + schemas, not adjacency.** A canonical slug
   renders *mechanically* per ecosystem (§5); shared wire/domain contracts live once in
   `libs/protocols` (Protobuf).

## 2. Environment ≠ Platform

The single most load-bearing distinction (cited by 01 P6, 02 §1). Keep the axes separate or the
SDLC rots.

| | **Platform** | **Environment** |
|---|---|---|
| Answers | *Where/how does the artifact run?* | *Which stage am I serving?* |
| Kind | a **port** — `docker-compose` \| `kubernetes` \| `bare-host` \| `vm` | an **enum** — `development` \| `test` \| `staging` \| `production` |
| Selects | the mechanism that runs/wires the *same artifact* | configuration values, secret source, telemetry endpoints, scale — never mechanism |
| Detected via | `EDEN_PLATFORM`, else `KUBERNETES_SERVICE_HOST`, else compose label, else bare-host | `EDEN_ENVIRONMENT` |
| Default map | development→docker-compose · test→docker/kind · staging→kubernetes · production→kubernetes | the four stages |

Staging and production are the **same platform** at different stages — proof the axes are
independent. The map is a default policy table, not a coupling.

**The hard rule:** no `if environment == "production"` in business code, ever. Stage selects
*injected wiring* at the composition root only; platform selects *which adapter is bound*.
`New(configuration, dependencies)` stays pure.

**Self-hosting payoff:** the `platform` port *is* `workspaceprovider` generalized — Eden runs
itself (`eden up`) through the same substrate abstraction it sells (F1, 05 §2). The environment
value is stamped onto the OpenTelemetry Resource as **`deployment.environment.name`** (the Stable
attribute — not the deprecated `deployment.environment`).

## 3. Top-level folder architecture (language-first)

```
eden/                                    (the monorepo; apps live here)
├── go.work                              # DEV-ONLY, gitignored (ADR-0009 C) — spans apps/* + libs/go/*
├── apps/
│   ├── backend/                         # Go — control-plane modular monolith (eden up local + server)
│   ├── frontend/                        # Svelte — one bundle: web AND inside Tauri (ADR-0004)
│   ├── desktop/                         # Rust + Tauri v2 — wraps the frontend bundle
│   └── agent/                           # Go — the dial-out in-workspace agent
├── infrastructure/kubernetes/
│   ├── base/                            # one definition of the artifact
│   └── overlays/{test,staging,production}/   # kustomize: patch values per stage, never mechanism
└── libs/                               (submodule → gophersys/libs; partitioned by ecosystem)
    ├── protocols/                       # Protobuf + buf — the cross-language source of truth
    ├── go/                              # ← to be created in WS1 (09 §2); one go.mod per library
    ├── typescript/                      # @eden/* npm packages (yarn 4 workspace)
    ├── rust/                            # eden-* cargo crates (cargo workspace)
    ├── python/                          # eden-* PyPI packages (peripheral, future)
    ├── zephyr/                          # eden-* west modules (future; embedded is the last cell)
    └── dart/                            # eden_* pub packages (future; created when the mobile cell lands)
```

> `libs/` is the `gophersys/libs` repo; `apps/` is the eden monorepo. **Two git repos = two
> module roots** (ADR-0009 B) — precisely what mechanically forces published-version consumption
> with a local override.

## 4. Canonical pattern catalogue

Each pattern = a **port** (interface contract) + a **discipline** (an invariant it enforces).
Contracts are language-neutral; ecosystems render them idiomatically. The spine:

```
New(configuration, dependencies) -> (Component, error)   // PURE: no I/O, clocks, or env reads
```

| Slug | Universal? | Purpose (one line) |
|---|---|---|
| `configuration` | Universal | Immutable, fully-resolved input IR; parsed once at the edge, then frozen. |
| `dependencies` | Universal | The injected record of ports (`Clock`, `RandomSource`, `Sink`, …); the hexagon (ADR-0009 A). |
| `errors` | Universal | Typed, wrappable, inspectable, redaction-safe error model with a stable `Kind`. |
| `observability` | Universal | Structured **Event** stream (model/tool calls, phases, cost, gates), OTel-aligned, secret-safe. |
| `logging` | Universal | Operator-facing leveled lines; a subordinate Sink over `observability`. |
| `testing` | Universal | A canonical **fake for every port** + a conformance suite proving adapter≡fake substitutability (08 §2). |
| `secrets` | Near-universal | Provider port resolving opaque **references** → values at point-of-use; values never logged/telemetered (07 §2). |
| `management` | Near-universal | The **dial-out-only** plane: outbound link, commands in / telemetry out, *no listening socket* (07 §3). |
| `transport` | Domain-shaped | Functional request/response + streaming boundary; schemas owned by `libs/protocols`. |
| `environment` | Cross-cutting | Stage enum + `EDEN_ENVIRONMENT` detection + per-stage configuration/secret/telemetry selection (§2). |
| `platform` | Cross-cutting | Runtime-substrate port; = `workspaceprovider` generalized (§2). |
| `evidence` | Domain-specific | Clean-room verification envelope; the verifier never sees what the implementer wrote (02 §2). |
| `persistence` | Domain-specific | Consumer-defined Repository + transactional Unit-of-Work + outbox. Backend/embedded-linux only. |
| `identity` | Domain-specific | AuthN (verify principal) + AuthZ (authorize action); workload-identity / SPIFFE-style. |

**A domain is a recipe** over these: `cloud-backend` = configuration + dependencies + errors +
observability + logging + secrets + transport + persistence + identity + management + testing.
`native-ui` = configuration + dependencies + errors + observability + transport(client) + testing,
and *consumes* identity/secrets rather than providing them. `embedded-rtos` *(future)* =
configuration + dependencies + errors + observability + management(dial-out) + testing — no
persistence, no identity-issuing.

Selected contracts (illustrative):

```
# secrets — the enforcement is in the TYPE: a Secret is constructed un-printable.
SecretReference                                   // opaque, loggable handle, lives in configuration
SecretProvider.Resolve(SecretReference) -> (Secret, error)
Secret.Use(fn(bytes) -> T) -> T                   // scoped exposure
Secret.String() -> "***REDACTED***"               // String/Debug/JSON/log ALL redact, by type
Secret.Zeroize()                                  // best-effort wipe (mandatory on embedded)

# evidence — the information barrier: Verify has NO implementer-source parameter.
Verifier.Verify(Artifact, Specification, Attestations) -> Verdict
Verdict = { passed, policyId, evidenceRefs[], reason }

# management — opens NO listening socket.
ManagementLink.DialOut(controllerEndpoint, identity) -> (Session, error)   // OUTBOUND only, mTLS
Session.Commands() -> <-stream<Command>           // commands IN
Session.SendTelemetry(TelemetryFrame) -> error    // telemetry OUT
```

## 5. Full-naming standard (HNS-1)

A slug is the **join key**: `slug := word ("-" word)*`, `word := [a-z][a-z0-9]*`. Lowercase,
hyphen-separated, fully spelled out. Given a slug + ecosystem, the rendered name is a **pure
function** (no judgment at render time).

| Ecosystem | Partition | Package/dist name | In-code identifier | Disk path |
|---|---|---|---|---|
| **go** | `libs/go/` | module `github.com/gophersys/libs/go/<kebab>` | package = lowercase, no separators | `libs/go/<kebab>/` |
| **rust** | `libs/rust/` | `eden-<kebab>` | `use eden_<snake>` | `libs/rust/<kebab>/` |
| **typescript** | `libs/typescript/` | `@eden/<kebab>` | `@eden/<kebab>` | `libs/typescript/<kebab>/` |
| **dart** | `libs/dart/` | `eden_<snake>` | `package:eden_<snake>` | `libs/dart/<snake>/` |
| **zephyr** | `libs/zephyr/` | west module `eden-<kebab>` | `CONFIG_EDEN_<SCREAM>` | `libs/zephyr/<kebab>/` |
| **python** | `libs/python/` | dist `eden-<kebab>` | `from eden.<snake> import …` | `libs/python/<kebab>/` |

Worked: `secrets` → Go `…/libs/go/secrets` (`package secrets`) · Rust `eden-secrets` · TypeScript
`@eden/secrets` · Dart `eden_secrets` · Zephyr `CONFIG_EDEN_SECRETS` · Python `from eden.secrets`.

**Settled ambiguities:** `go` not `golang` · `typescript` not `ts` · `zephyr` (the toolchain) not
`rtos`/`c` · `configuration` for the slug (idiomatic exported Go *type names* such as `Config`
and `Deps` are exempt — type names, not pattern names) · `dependencies` as the hexagon slug
(ADR-0009 A) · `identity`
not `auth` (authN/authZ conflation) · `management` (dial-out plane) distinct from `transport`
(functional plane) · `environment` (stage) distinct from `platform` (substrate).

**Forbidden → required** (lint-enforced): `cfg/config`→`configuration` · `obsv/o11y`→
`observability` · `deps`→`dependencies` · `mgmt`→`management` · `auth`→`identity` ·
`db/repo/store`→`persistence` · `k8s`→`kubernetes` · `ts`→`typescript` · `golang`→`go` ·
`util/utils/common/core/misc`→ *banned outright* (name the actual pattern).

> Tool-imposed filenames are out of scope (`vite.config.ts`, the npm scope `@eden`, etc.).

## 6. Per-ecosystem library architecture

### 6.1 Go (priority) — `libs/go/`

- **One Go module per library** (own `go.mod`) — required for independent tag-prefixed
  versioning. No root `go.mod`.
- **Dev override = a single gitignored root `go.work`** (ADR-0009 C) that `use`s the in-repo
  modules + apps. No committed `replace`, ever.
- **Floor Go 1.26** (ADR-0003); tool versions pinned via the `tool` directive (golangci-lint v2,
  govulncheck, mockgen).
- **Publish = git tag**: `go/<library>/vX.Y.Z` within `gophersys/libs`, resolvable as
  `github.com/gophersys/libs/go/<library>@vX.Y.Z`.
- **Release builds use `GOWORK=off` and `CGO_ENABLED=0`** — a stray workspace can never mask a
  missing published version, and binaries are static.

```
libs/go/observability/
├── go.mod                  # module github.com/gophersys/libs/go/observability (go 1.26)
├── project.json  ctl.sh    # Nx wrappers → bash ./ctl.sh <verb>
├── observability.go        # Config (immutable) + Deps (ports) + New(Config, Deps) → (Provider, error)
├── event.go  provider.go   # the Event type + the outbound Provider port
├── internal/               # unexported impl
├── oteladapter/            # adapter: OTel/OTLP (slog + otelslog bridge)
├── slogadapter/            # adapter: collector-less stdlib slog
└── observabilitytest/      # public fakes (the testing pattern)
```

`ctl.sh` verbs (Go): `help validate build test lint typecheck vet vulncheck tidy generate fmt
cover dev-on dev-off verify release-check release adopt tools-sync`.

### 6.2 The other ecosystems (summary)

| Ecosystem | Dev-override marker (gitignored) | Publish target | Version source |
|---|---|---|---|
| **typescript** (Svelte 5 — ADR-0004; framework choices pending OD-1/2/3) | workspace link in a gitignored override file | publish to private registry (`workspace:*` rewritten) | `package.json` |
| **rust** | `[patch.crates-io] … { path = … }` at workspace root, hook-guarded | `cargo publish` (private registry) | `Cargo.toml` |
| **dart** *(future)* | `pubspec_overrides.yaml` | `dart pub publish` (or git) | `pubspec.yaml` |
| **zephyr** *(future)* | `west.local.yml` local `path:` (hardest case) | git tag + `west.yml` revision bump | `west.yml` revision |
| **python** *(future)* | gitignored `[tool.uv.sources] … editable=true` | `uv build && uv publish` | `pyproject.toml` |
| **protocols** | gitignored `buf.work.yaml` local module | `buf push` to the BSR | BSR module version |

## 7. The Eden app stack

### 7.1 `apps/backend` (Go, priority)

The control-plane modular monolith — one module (`github.com/gophersys/eden/apps/backend`,
ADR-0009 B), multiple `cmd/` entrypoints, domain logic in `internal/` partitioned **by domain**
(not by layer), consuming libs as published versioned dependencies. Subsystem slices per 03 §4.

The composition root is the **only** place the stage axis branches:

```go
stage, _ := environment.Detect(os.Getenv)     // axis A
plat,  _ := platform.Detect(os.Getenv)        // axis B
deps     := wiring.For(stage)                  // the ONLY switch on stage in the tree
env,   _ := environment.Resolve(stage, deps)
app      := backend.New(env.Config, backend.Deps{Secrets: deps.Secrets, Telemetry: obs, Platform: plat})
plat.Up(ctx, app)                              // docker-compose Up ≡ kubernetes Up — one binary, one image
```

Transport is **Connect** (gRPC + gRPC-Web + Connect-JSON) generated from `libs/protocols` via buf
managed mode — one service definition serves both the "gRPC backend" and "HTTP backend" archetype
needs (00 §5). The orchestrator is a level-based, idempotent `Reconcile(ctx, key)` consuming
`workspaceprovider.Provider` as a port, so substrate adapters are interchangeable and
contract-tested.

### 7.2 `apps/frontend` + `apps/desktop` (Svelte 5 + Rust/Tauri v2)

**One Vite bundle** ships as the web app *and* inside the Tauri WebView (ADR-0004). The seam is
`@eden/platform`'s **PlatformBridge** (ports + web/tauri adapters); the runtime is detected once
at startup, and the tauri adapters are dynamically imported so they tree-shake out of the web
bundle. Feature slices live in `apps/frontend/src/modules/*`, depend only on **ports**, and never
import each other.

- **Secrets on the client:** desktop → OS keychain via the `keyring` crate through `eden-native`
  commands; web → no browser keychain, secrets stay server-side, the client holds only
  short-lived tokens. (Tauri's Stronghold plugin is deprecated; do not use it.)
- **Native crates:** `libs/rust/eden-shell` (menu/tray/deep-link/updater) + `libs/rust/eden-native`
  (keychain/process/tunnel/fs). Tauri v2 **capabilities** scope every native command.
- **Backend seam:** `@eden/api` only (Connect-ES). Design system `@photosphere/*` consumed
  published, never vendored (ADR-0005).
- **Open (per the Svelte re-platform):** behavior layer (OD-1), SvelteKit vs Vite SPA (OD-2),
  state/query/machine layers (OD-3).

## 8. Dev → release → adopt lifecycle + enforcement

State machine per library, tracked by two independent facts: **override state** (app wired to
source or remote?) and **release state** (does a published version exist?).

```
AUTHORED ──dev──▶ OVERRIDE ──release──▶ RELEASED ──adopt──▶ ADOPTED
            ◀─undev─                                  ◀── merge gate requires ADOPTED
```

**Merge invariant:** on `main`, every app↔library edge must be **ADOPTED** (remote-pinned).
Enforced mechanically.

**Universal `ctl.sh` verbs** (same names everywhere; mechanism is language-bound): `dev`/`undev`,
`build`, `test`, `lint`, `release`, `adopt`, `status`, `verify`. `status` is the keystone oracle —
one JSON line, **exit 3 when an override is active**, so every hook branches without parsing.

**Enforcement (defense in depth):**
1. Override markers (`go.work`, `pubspec_overrides.yaml`, …) are **`.gitignore`d** — cannot be
   committed by accident.
2. A tracked `.githooks/pre-commit` blocks staged override markers; `pre-push` runs `status` for
   every library and refuses a push to `main` if any override is active.
3. **CI re-runs the identical check** (client hooks are bypassable with `--no-verify`; the server
   gate is not).
4. **`project-<ecosystem>` Claude Code plugins** (+ a shared `project-enforcement`): `PreToolUse`
   guard on `git commit`/`push`, `PostToolUse` manifest-guard on edits, `SessionStart` injection
   of current override state. ~60% of enforcement abstracts to `project-enforcement`; only
   override-file syntax, the publish command, and the version field differ per ecosystem.

Plugins live at `libs/plugins/project-<ecosystem>/` with a `libs/.claude-plugin/marketplace.json`.

## 9. Interface / API-design discipline

> **Knowledge ≠ enforcement** (= P7). `.claude` knowledge *guides* authoring; deterministic
> linters + breaking-change gates *enforce*. Breaking a published interface is the cardinal sin.

- **Network/API** (`libs/protocols`): governed by **AIPs** (aip.dev) — resource-oriented design
  (AIP-121/122), standard methods (131–135), field naming (140), enums (126), pagination (158),
  the `google.rpc.Status` error model (193), versioning (185). Enforced by `buf lint` + Google
  `api-linter` + `buf breaking` (gate uses `WIRE_JSON`, matching all three Connect transports;
  `FILE` advisory locally).
- **Code-level** (per ecosystem): small, composable, consumer-defined interfaces — "accept
  interfaces, return concrete." Go → golangci-lint `interfacebloat`(max 5) + `ireturn` + `revive`;
  Rust → Rust API Guidelines + `clippy` + `cargo-semver-checks`; Svelte/TypeScript → exported-API
  diff via the chosen toolchain (pending OD-3 ruling). Each ecosystem wires a `ctl.sh api-check`
  verb (semver/breaking diff on exported symbols).
- **3-layer model:** (A) neutral principles once in `libs/.claude/rules/`; (B) per-ecosystem
  rendering in each `project-<ecosystem>` plugin's skill; (C) tooling enforcement via `ctl.sh
  lint`/`api-check` run by a `PostToolUse` hook **and** the CI gate — one source of truth, two
  trigger points.
- **Self-hosting payoff:** the same skills feed the kernel's resolved agent context, so generated
  features are AIP/interface-compliant by construction — and because Eden consumes its own
  *published* protocols, `buf breaking` literally stops the build system from amputating itself.
  The override-never-reaches-main rule and the breaking-change gate are the same safety property.

## 10. Build order

Build order is **owned by the ladder (06) and the workstreams (09 §2)**; this section defers to
them entirely (it exists for citation stability). The manifest below (§12) is sequenced
accordingly: the pattern libraries and kernel are L0 (hand-built), the control-plane libraries
are L1 task inventory, and the client stack enters at L2.

## 11. Decisions (formerly "open decisions A–F")

All six ruled — see **ADR-0009**: A `dependencies` slug · B module roots
(`github.com/gophersys/eden/...` apps, `github.com/gophersys/libs/go/<library>` libs) · C root
gitignored `go.work` · D agentd U1 as gated donor material · E `bare-host` · F docs-first.

## 12. Library manifest (what to build, per partition)

### Language map

| Partition | Language | What lives here |
|---|---|---|
| `libs/protocols/` | Protobuf (buf) | the API + cross-language domain contract — the source of truth |
| `libs/go/` | Go 1.26 | the control plane **and** the build-system kernel |
| `libs/typescript/` | TypeScript (strict) + Svelte 5 | the client-shared libraries (`@eden/*`) |
| `libs/rust/` | Rust | the Tauri v2 desktop shell + native capability crates |
| `libs/python/` | Python | ML/eval + automation tooling (future) |
| `libs/zephyr/` | C / Zephyr | embedded firmware (future; the last cell) |
| *(separate repo)* | TypeScript + Svelte | `gophersys/photosphere` — the design system (`@photosphere/*`), consumed published |

### `libs/go/` — control plane

| Library | Purpose |
|---|---|
| `workspaceprovider` | The core substrate interface + adapters: `docker-compose` · `kubernetes` · later: `vm` (Firecracker/KubeVirt) · `bare-host` · `mac` (Orka) · `gpu`. Contract-tested as interchangeable. |
| `orchestrator` | Workspace lifecycle reconcile loop (controller pattern: desired vs actual) |
| `broker` | Connection/tunnel coordination — WireGuard mesh + DERP relay fallback; compose **Tailscale/tsnet** rather than reimplementing |
| `identity` | OIDC/SSO, RBAC, organizations/users |
| `templates` | Versioned environment registry (devcontainer-compatible) |
| `policy` | Quotas, cost, idle/hibernate, pre-warm pools |
| `audit` | Append-only audit log (07 §7) |
| `gateway` | The Connect API surface + PTY/file/port streams, from `protocols` |

### `libs/go/` — build-system kernel (06 L0)

| Library | Owns |
|---|---|
| `agentconfiguration` | Config + routing + the LLM call binding: model + auth per role; compiles to harness formats (upstream design: agentcfg-architecture) |
| `evidence` | The Evidence **interface** + concrete impls (`GoTestEvidence` first) |
| `specification` | `Spec = {Contract, Template-ref, Tests, Gate}` — four roles behind interfaces |
| `template` | Per-cell scaffolds (typed holes: interface + `panic("unimplemented")` + `_test.go` first) |
| `codingharness` | The implementing loop — F4 adapter driving Claude Code first (ADR-0008) |
| `testharness` | Clean-environment provision + exercise + emit Evidence (anti-reward-hack, 07 §4) |
| `engine` | Walks the linear phase chain; binds phase→model via `agentconfiguration`; holds mutable run-state |
| `cell` | The typed Cell schema (D1–D5 + topology + ports) + the cell-invariant validator. Post-L0: formalized at L1 — the linear L0 engine hardcodes the go-backend cell (build-system invariant I11) |

> `evidence`, `agentconfiguration`, and `cell` are shared by the kernel *and* the control plane's
> gates — the concrete reason `libs/go/` exists rather than burying them in one app.

### `libs/typescript/` — `@eden/*` (Svelte 5)

| Library | Purpose | Notes |
|---|---|---|
| `@eden/domain` | Domain types + pure logic from proto. No framework, no network. | generated from `protocols` |
| `@eden/api` | Connect-ES clients + typed facades — the only backend seam | framework-agnostic |
| `@eden/state` | Cross-cutting stores: auth, connection, theme, command registry | Svelte 5 runes; final shape OD-3 |
| `@eden/commands` | Unified command registry → menubar + ⌘K palette + shortcuts | — |
| `@eden/platform` | PlatformBridge ports/adapters (Tauri vs web): keychain, process, tunnel, fs, deep-links | `@tauri-apps/api` |
| `@eden/machines` | Lifecycle machines mirroring backend workspace state | OD-3 (XState's Svelte adapter vs runes) |
| `@eden/testing` | Fixtures, fakes, render helpers, Connect mocks | vitest + Svelte testing library |
| `@eden/tsconfig` / `@eden/lint-config` | Shared compiler/lint presets | toolchain pending OD-3 |

### `libs/rust/`

| Crate | Purpose |
|---|---|
| `eden-shell` | Tauri v2 desktop shell: native menubar, windows, tray, deep links, auto-updater |
| `eden-native` | Capability crates behind `@eden/platform`'s Tauri adapter: OS keychain, process spawn, client-side tunnel, fs |

### `apps/` (deployables, not libraries)

| App | Language | Imports |
|---|---|---|
| `apps/backend` | Go | `libs/go/*` — the control-plane modular monolith (§7.1) |
| `apps/frontend` | Svelte 5 | `libs/typescript/*` + `@photosphere/*` (§7.2) |
| `apps/desktop` | Rust (Tauri v2) | `libs/rust/eden-shell` wrapping the frontend bundle |
| `apps/agent` | Go | the dial-out workspace agent (`management` pattern; static, `CGO_ENABLED=0`; donor: `poc/agents`) |
