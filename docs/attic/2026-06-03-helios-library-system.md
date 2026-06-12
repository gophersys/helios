# Helios Library System — Architecture

> Synthesized from a 14-agent research swarm (fact-checked against 2025–2026 sources).
> Companion to `LIBRARIES.md` (the *what to build* map); this is the *how it's structured,
> named, consumed, and enforced* doc. A planning artifact — not yet committed to `gophersys/libs`.

---

## 1. Principles

1. **Self-hosting.** Helios is a software-engineering tool built *on* a core set of first-principles
   libraries; apps built *with* Helios consume the same libraries. Helios builds on Helios.
2. **Language-first.** Libraries are partitioned by ecosystem (`libs/<ecosystem>/…`) because packaging,
   versioning, publishing, dependency resolution and the local↔remote dev swap are all language-bound.
   A **domain** (cloud-backend, embedded-rtos, native-ui) is a *recipe* that composes patterns — never a
   directory tier.
3. **Dogfooded consumption.** The monorepo's own apps consume libraries from their **published remote**
   versions, *never* from source — except during active library development, when a local override
   points the app at in-repo source. **The override must never reach `main`.**
4. **Full naming, no abbreviations.** `typescript` not `ts`, `observability` not `obsv`, `configuration`
   not `config`, `kubernetes` not `k8s`, `dependencies` not `deps`. Enforced by a lint hook.
5. **Hexagonal everywhere.** Every library exposes a pure `New(configuration, dependencies)` — no I/O,
   clocks, or env reads inside; every side effect lives behind an injected port. This is the agentd
   contract, generalized to the whole system.
6. **Cross-language coherence comes from names + schemas, not adjacency.** A canonical slug renders
   *mechanically* per ecosystem; shared wire/domain contracts live once in `libs/protocols` (Protobuf).

---

## 2. Two orthogonal axes: Environment ≠ Platform

The single most load-bearing distinction. Keep them separate or the SDLC rots.

| | **Platform** | **Environment** |
|---|---|---|
| Answers | *Where/how does the artifact run?* | *Which stage am I serving?* |
| Kind | a **port** — `docker-compose` \| `kubernetes` \| `bare-host` \| `vm` | an **enum** — `development` \| `test` \| `staging` \| `production` |
| Selects | the mechanism that runs/wires the *same artifact* | configuration values, secret source, telemetry endpoints, scale — never mechanism |
| Detected via | `HELIOS_PLATFORM`, else `KUBERNETES_SERVICE_HOST`, else compose label, else bare-host | `HELIOS_ENVIRONMENT` |
| Helios default map | dev→docker-compose · test→docker/kind · staging→kubernetes · production→kubernetes | the four stages |

Staging and production are the **same platform** (k8s), different environments — proof the axes are
independent. The mapping is a **default policy table, not a coupling**: `test` can run on `kind`
(the kubernetes adapter) at `HELIOS_ENVIRONMENT=test`.

**The hard rule that falls out:** there is **no `if environment == "production"` in business code, ever.**
Stage selects *injected wiring* at the composition root only; platform selects *which adapter is bound*.
`New(configuration, dependencies)` stays pure. This is 12-factor "config in the environment" + "dev/prod
parity" made literal.

**Self-hosting payoff:** the `platform` port *is* `workspaceprovider` generalized — Helios runs *itself*
(`helios up`) through the same substrate abstraction it sells customers.

`environment` and `platform` become two **canonical patterns** (§4) and two shared libraries per ecosystem.
The environment value is stamped onto the OpenTelemetry Resource as **`deployment.environment.name`**
(Stable; note: *not* the deprecated `deployment.environment`).

---

## 3. Top-level folder architecture (language-first)

```
helios/                                  (the monorepo; apps live here)
├── go.work                              # DEV-ONLY, gitignored — spans apps/* + libs/go/* during dev
├── apps/
│   ├── backend/                         # Go — control-plane modular monolith (helios up local + k8s server)
│   ├── frontend/                        # TypeScript + React 19 — one bundle: web AND inside Tauri
│   ├── desktop/                         # Rust + Tauri v2 — wraps the frontend bundle
│   └── agent/                           # Go — the dial-out in-workspace agent (agentd)
├── infrastructure/kubernetes/
│   ├── base/                            # one definition of the artifact
│   └── overlays/{test,staging,production}/   # kustomize: patch values per stage, never mechanism
└── libs/                               (submodule → gophersys/libs; partitioned by ecosystem)
    ├── protocols/                       # Protobuf + buf — the cross-language source of truth
    ├── go/                              # Go modules (multi-module; one go.mod per library)
    ├── typescript/                      # @helios/* npm packages (yarn 4 workspace)
    ├── rust/                            # helios-* cargo crates (cargo workspace)
    ├── dart/                            # helios_* pub packages (Flutter is a recipe over Dart)
    ├── zephyr/                          # helios-* west modules (C / Kconfig)
    └── python/                          # helios-* PyPI packages (peripheral)
```

> `libs/` is the `gophersys/libs` git repo; `apps/` is the Helios monorepo. **Two git repos = two module
> roots**, which is precisely what forces published-version consumption with a local override.

---

## 4. Canonical pattern catalogue

Each pattern = a **port** (interface contract) + a **discipline** (an invariant it enforces). Contracts
are language-neutral; ecosystems render them idiomatically. The spine:

```
New(configuration, dependencies) -> (Component, error)   // PURE: no I/O, clocks, or env reads
```

| Slug | Universal? | Purpose (one line) |
|---|---|---|
| `configuration` | Universal | Immutable, fully-resolved input IR; parsed once at the edge, then frozen. |
| `dependencies` | Universal | The injected record of ports (`Clock`, `RandomSource`, `Sink`, …); the hexagon. |
| `errors` | Universal | Typed, wrappable, inspectable, redaction-safe error model with a stable `Kind`. |
| `observability` | Universal | Structured **Event** stream (model/tool calls, phases, cost, gates), OTel-aligned, secret-safe. |
| `logging` | Universal | Operator-facing leveled lines; a subordinate Sink over `observability`. |
| `testing` | Universal | A canonical **fake for every port** + a conformance suite proving adapter≡fake substitutability. |
| `secrets` | Near-universal | Provider port resolving opaque **references** → values at point-of-use; values *never* logged/telemetered. |
| `management` | Near-universal | The **dial-out-only** plane: outbound link, commands in / telemetry out, *no listening socket*. |
| `transport` | Domain-shaped | Functional request/response + streaming boundary; schemas owned by `libs/protocols`. |
| `environment` | Cross-cutting | Stage enum + `HELIOS_ENVIRONMENT` detection + per-stage config/secret/telemetry selection. |
| `platform` | Cross-cutting | Runtime-substrate port (`docker-compose`/`kubernetes`/`bare-host`/`vm`); = `workspaceprovider` generalized. |
| `evidence` | Domain-specific | Clean-room verification envelope; the verifier never sees what the implementer wrote (SLSA-VSA model). |
| `persistence` | Domain-specific | Consumer-defined Repository + transactional Unit-of-Work + outbox. Backend/embedded-linux only. |
| `identity` | Domain-specific | AuthN (verify principal) + AuthZ (authorize action); workload-identity / SPIFFE-style. |

**A domain is a recipe** over these: `cloud-backend` = configuration + dependencies + errors + observability +
logging + secrets + transport + persistence + identity + management + testing. `embedded-rtos` = configuration +
dependencies + errors + observability + management(dial-out) + testing (no persistence, no identity-issuing).
`native-ui` = configuration + dependencies + errors + observability + transport(client) + testing, and *consumes*
identity/secrets rather than providing them.

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

---

## 5. Full-naming standard (HNS-1)

A slug is the **join key**: `slug := word ("-" word)*`, `word := [a-z][a-z0-9]*`. Lowercase, hyphen-separated,
fully spelled out. Given a slug + ecosystem, the rendered name is a **pure function** (no judgment at render time).

| Ecosystem | Partition | Package/dist name | In-code identifier | Disk path |
|---|---|---|---|---|
| **go** | `libs/go/` | module `github.com/gophersys/libs/go/<kebab>` | package = lowercase, no separators | `libs/go/<kebab>/` |
| **rust** | `libs/rust/` | `helios-<kebab>` | `use helios_<snake>` | `libs/rust/<kebab>/` |
| **dart** | `libs/dart/` | `helios_<snake>` | `package:helios_<snake>` | `libs/dart/<snake>/` |
| **typescript** | `libs/typescript/` | `@helios/<kebab>` | `@helios/<kebab>` | `libs/typescript/<kebab>/` |
| **zephyr** | `libs/zephyr/` | west module `helios-<kebab>` | `CONFIG_HELIOS_<SCREAM>` | `libs/zephyr/<kebab>/` |
| **python** | `libs/python/` | dist `helios-<kebab>` | `from helios.<snake> import …` | `libs/python/<kebab>/` |

Worked: `secrets` → Go `…/libs/go/secrets` (`package secrets`) · Rust `helios-secrets` (`use helios_secrets`) ·
Dart `helios_secrets` · TS `@helios/secrets` · Zephyr `CONFIG_HELIOS_SECRETS` · Python `from helios.secrets`.

**Settled ambiguities:**
- **`go`**, not `golang` — "Go" is the language's real name; `golang` is a domain/SEO artifact. The toolchain is `go`.
- **`typescript`**, not `ts`. **`rust`/`python`/`dart`** are already real names. **`zephyr`** (the toolchain), not `rtos`/`c`.
- **`configuration`** for the directory/module/slug. The Go **package** is `configuration` (not an abbreviation, so allowed);
  the idiomatic exported struct type may be `Config` (a type name, not the pattern name).
- **`dependencies`** as the hexagon slug (matches `New(configuration, dependencies)`); `ports` is the architectural
  concept it contains. *(See Open Decision A.)*
- **`identity`** not `auth` (which fatally conflates authN/authZ). **`management`** (the dial-out plane) distinct from
  **`transport`** (the functional plane). **`environment`** (stage) distinct from **`platform`** (substrate).

**Forbidden → required** (lint-enforced): `cfg/config`→`configuration`, `obsv/o11y`→`observability`,
`deps`→`dependencies`, `mgmt`→`management`, `auth`→`identity`, `db/repo/store`→`persistence`, `k8s`→`kubernetes`,
`ts`→`typescript`, `golang`→`go`, and `util/utils/common/core/misc`→ *banned outright* (name the actual pattern).

> Tool-imposed filenames are out of scope (e.g. `vite.config.ts`, `*.go` extension, npm scope `@helios`).

---

## 6. Per-ecosystem library architecture

### 6.1 Go (priority) — `libs/go/`

- **One Go module per library** (own `go.mod`) — required for independent tag-prefixed versioning. No root `go.mod`.
- **Dev override = a single gitignored `go.work`** that `use`s the in-repo modules + apps. No committed `replace` ever.
- **Floor Go 1.24**; tool versions pinned via the **`tool` directive** (golangci-lint v2, govulncheck, mockgen).
- **Publish = git tag** (Go has no registry): tag `go/<lib>/vX.Y.Z` **within the `gophersys/libs` repo**
  (the module subdir there is `go/<lib>/`), resolvable as `github.com/gophersys/libs/go/<lib>@vX.Y.Z`.
- **Release builds use `GOWORK=off`** so a stray workspace can never mask a missing published version.

```
libs/go/observability/
├── go.mod                  # module github.com/gophersys/libs/go/observability (go 1.24)
├── project.json  ctl.sh    # Nx wrappers → bash ./ctl.sh <verb>
├── observability.go        # Config (immutable) + Deps (ports) + New(Config, Deps) → (Provider, error)
├── event.go  provider.go   # the Event type + the outbound Provider port
├── internal/               # unexported impl
├── oteladapter/            # adapter: OTel/OTLP (slog + otelslog bridge)
├── slogadapter/            # adapter: collector-less stdlib slog
└── observabilitytest/      # public fakes (the testing pattern)
```

`ctl.sh` verbs (Go): `help validate build test lint typecheck vet vulncheck tidy generate fmt cover
dev-on dev-off verify release-check release adopt tools-sync`.

### 6.2 The other ecosystems (summary; detail in the per-agent findings)

| Ecosystem | Dev-override marker (gitignored) | Publish target | Version source |
|---|---|---|---|
| **typescript** | `pnpm.overrides`/workspace link in a gitignored file | `pnpm publish` (private registry; `workspace:*` rewritten) | `package.json` version |
| **rust** | `[patch.crates-io] … { path = … }` at workspace root, hook-guarded | `cargo publish` (private registry) | `Cargo.toml` version |
| **dart** | `pubspec_overrides.yaml` (Dart's purpose-built local override) | `dart pub publish` (or git) | `pubspec.yaml` version |
| **zephyr** | `west.local.yml` import / local `path:` (hardest case) | git tag + `west.yml` revision bump | `revision` tag in `west.yml` |
| **python** | gitignored `[tool.uv.sources] … editable=true` | `uv build && uv publish` | `pyproject.toml` version |
| **protocols** | gitignored `buf.work.yaml` local module | `buf push` to BSR | BSR module version |

---

## 7. The Helios app stack

### 7.1 `apps/backend` (Go, priority)

The control-plane modular monolith — **one module** (`github.com/gophersys/helios/apps/backend`, *see Open Decision C*),
multiple `cmd/` entrypoints, domain logic in `internal/` partitioned **by domain** (not by layer), consuming libs as
**published versioned dependencies**.

```
apps/backend/
├── go.mod  project.json  ctl.sh
├── cmd/helios/main.go            # composition root: detect stage+platform, wire deps, run.Group
├── internal/
│   ├── app/{app.go,deps.go,run.go}   # New(cfg, deps) pure; run.Group of controllers
│   ├── workspaces/  identity/  policy/  templates/  audit/   # one domain slice each
│   └── config/config.go
└── deploy/Dockerfile             # GOWORK=off, CGO_ENABLED=0
```

The composition root is the **only** place the stage axis branches:

```go
stage, _ := environment.Detect(os.Getenv)     // axis A
plat,  _ := platform.Detect(os.Getenv)        // axis B
deps     := wiring.For(stage)                  // the ONLY switch on stage in the tree
env,   _ := environment.Resolve(stage, deps)
app      := backend.New(env.Config, backend.Deps{Secrets: deps.Secrets, Telemetry: obs, Platform: plat})
plat.Up(ctx, app)                              // docker-compose Up ≡ kubernetes Up — one binary, one image
```

Transport is **Connect** (gRPC + gRPC-Web + Connect-JSON) generated from `libs/protocols` via buf managed mode.
The orchestrator is a level-based, idempotent `Reconcile(ctx, key)` consuming `workspaceprovider.Provider` as a port,
so docker/kubernetes/vm/mac/gpu are interchangeable and contract-tested.

### 7.2 `apps/frontend` + `apps/desktop` (TypeScript/React 19 + Rust/Tauri v2)

**One Vite bundle** ships as the web app *and* inside the Tauri WebView. The seam is `@helios/platform`'s
**PlatformBridge** (ports + web/tauri adapters); the runtime is detected **once** at startup
(`'isTauri' in window && window.isTauri === true`), and the tauri adapters are dynamically imported so they
tree-shake out of the web bundle. Feature slices live in `apps/frontend/src/modules/*`, depend only on **ports**,
and never import each other.

- **Secrets on the client:** desktop → `keyring` crate (macOS Keychain / Windows Credential Manager / libsecret)
  via `helios-native` commands; web → **no browser keychain**, secrets stay server-side, client holds only short-lived
  tokens. (Stronghold is deprecated; do not use it.)
- **Native crates:** `libs/rust/helios-shell` (menu/tray/deep-link/updater) + `libs/rust/helios-native` (keychain/
  process/tunnel/fs). Tauri v2 **capabilities** scope every native command.
- **Backend seam:** `@helios/api` only, via Connect-ES v2 + connect-query-es v2 (TanStack Query). Design system
  `@photosphere/*` (React Aria + vanilla-extract) consumed, never vendored.

---

## 8. Dev → release → adopt lifecycle + AI instrumentation

State machine each library moves through, tracked by two independent facts: **override state** (app wired to source
or remote?) and **release state** (does a published version exist?).

```
AUTHORED ──dev──▶ OVERRIDE ──release──▶ RELEASED ──adopt──▶ ADOPTED
            ◀─undev─                                  ◀── merge gate requires ADOPTED
```

**Merge invariant:** on `main`, every app↔lib edge must be in **ADOPTED** (remote-pinned) state. Enforced mechanically.

**Universal `ctl.sh` verbs** (same names everywhere; mechanism is language-bound): `dev`/`undev`, `build`, `test`,
`lint`, `release`, `adopt`, `status`, `verify`. `status` is the keystone oracle — emits one JSON line and **exits 3
when an override is active**, so every hook branches without parsing.

**Enforcement (defense in depth):**
1. Override markers (`go.work`, `pubspec_overrides.yaml`, …) are **`.gitignore`d** — can't be committed by accident.
2. A tracked `.githooks/pre-commit` blocks staged override markers / committed path-overrides; `pre-push` runs
   `status` for every lib and **refuses a push to `main`** if any override is active.
3. **CI re-runs the identical check** (client hooks are bypassable with `--no-verify`; the server gate is not).
4. **`project-<ecosystem>` Claude Code plugins** (+ a shared `project-common`) add a `PreToolUse` guard on
   `git commit`/`push`, a `PostToolUse` manifest-guard on edits, and a `SessionStart` context injection of current
   override state. ~60% of enforcement abstracts to `project-common`; only override-file syntax, the publish command,
   and the version field truly differ per ecosystem.

Plugins live at `libs/plugins/project-<ecosystem>/` with a `libs/.claude-plugin/marketplace.json`.

---

## 9. Interface / API-design discipline + global enforcement

> **Knowledge ≠ enforcement.** `.claude` *guides* authoring; deterministic linters + breaking-change gates *enforce*.
> Both, layered. **Breaking a published interface is the cardinal sin** — that's where the real teeth are.

**Two levels:**

- **Network/API** (`libs/protocols`, "à la Google"): governed by **AIPs** (aip.dev) — resource-oriented design
  (AIP-121/122), standard methods (131–135), field naming (140), enums (126), pagination (158), the
  `google.rpc.Status` error model (193), versioning (185). Enforced by **`buf lint` + Google `api-linter` +
  `buf breaking`**. Breaking gate uses **`WIRE_JSON`** (matches all three Connect transports), `FILE` advisory locally.
- **Code-level** (per ecosystem): *small, composable, consumer-defined interfaces — "accept interfaces, return
  concrete."* Go → golangci-lint `interfacebloat`(max 5)+`ireturn`+`revive`; Rust → Rust API Guidelines + `clippy` +
  `cargo-semver-checks`; Dart → Effective Dart + `dart analyze`; Zephyr → opaque-struct header ABI. Each wires a
  **`ctl.sh api-check`** verb (semver/breaking diff on exported symbols).

**3-layer model:** (A) neutral principles live once in `libs/.claude/rules/10-api-design-principles.md` +
`11-interface-compatibility.md`, `@import`ed by `libs/CLAUDE.md`. (B) per-ecosystem rendering lives in each
`project-<ecosystem>` plugin's `skills/api-design/SKILL.md`. (C) tooling enforcement is `ctl.sh lint`/`api-check`
run by a `PostToolUse` hook **and** the CI gate — one source of truth, two trigger points.

**Self-hosting payoff:** the same `skills/api-design/SKILL.md` feeds the agent build-system's `ResolvedSkills`, so
generated features are AIP/interface-compliant **by construction**, and the gate guarantees it where construction
drifts. Because Helios consumes its own *published* protocols, `buf breaking` literally stops the build-system from
amputating itself — the override-never-reaches-main rule and the breaking-change gate are the same safety property.

---

## 10. Build order (first steps)

```
protocols ─┬─▶ libs/go: configuration · dependencies · errors · observability · secrets · testing
           │            └▶ workspaceprovider(docker) ▶ orchestrator ▶ broker ▶ gateway ─▶ apps/backend
           ├─▶ libs/typescript: domain ▶ api ▶ state/commands/platform ─────────────────▶ apps/frontend ─▶ M0
           └─▶ environment + platform (both go & typescript) wired at the composition roots
apps/desktop (Rust shell + libs/rust/*) wraps the bundle once it runs in the browser.
```

Priority: the **Go backend** + the **Helios UI/desktop/web**. Start the Go partition with the universal patterns
(`configuration`, `dependencies`, `errors`, `observability`, `secrets`, `testing`) since everything else composes them.

---

## 11. Open decisions (need your ruling)

| # | Decision | Recommendation |
|---|---|---|
| **A** | Hexagon slug: `dependencies` vs `ports` (agents split). | `dependencies` — matches `New(configuration, dependencies)`; expose a `ports` namespace inside it. |
| **B** | `apps/backend` repo/module path (apps live in the Helios monorepo, a *different* repo than the `gophersys/libs` submodule). | Confirm the Helios monorepo's module root, e.g. `github.com/gophersys/helios/apps/backend`. |
| **C** | The dev `go.work` location — `libs/go/go.work` vs a Helios-monorepo-root `go.work` spanning `apps/*` + `libs/go/*`. | Root-level (it must link apps *and* the libs submodule); gitignored. |
| **D** | Resurrect the parked **agentd U1** (branch `feat/go-agentd-u1`) as the first `libs/go/` library, now renamed per HNS-1 (`agentcfg`→`agentconfiguration`), or rebuild fresh? | Resurrect + rename — it already embodies the patterns. |
| **E** | Non-container substrate adapter name: `bare-host` vs `bare-metal`. | `bare-host` (it may be a VM guest), unless the only target is true hardware. |
| **F** | Begin scaffolding now (subtree `.gitkeep`s → patterns → `project-<ecosystem>` plugins), or iterate this doc first? | Your call. |
```
