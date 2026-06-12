# Helios — Library Manifest

> What to build, in what language, mapped onto the existing Nx monorepo
> (`libs/` = the `gophersys/libs` submodule, partitioned by language). A planning doc, not committed.
> Sources: `HELIOS.md`, `HELIOS-CLIENT.md`, the ADRs in `gophersys/photosphere/docs/adr/`, and the
> agentic-engineering corpus (`~/Documents/research/agentic-engineering/`,
> `~/Documents/Claude/Projects/Helios/spec-driven-implementation-system.md`).

## TL;DR — the language map

| Partition | Language | What lives here |
|---|---|---|
| `libs/protocols/` | **Protobuf** (buf) | the API + cross-language domain contract — the source of truth |
| `libs/typescript/` | **TypeScript (strict) + React 19** | the client-shared libraries (`@helios/*`) |
| **`libs/go/`** ← **MISSING, add it** | **Go 1.24+** | the control plane **and** the agent build-system engine |
| `libs/rust/` | **Rust** | the Tauri v2 desktop shell + native capability crates |
| `libs/python/` | **Python** | ML/eval + automation tooling (future; the model series' ML cell) |
| `libs/zephyr/` | **C / Zephyr** | embedded firmware (future; the last discipline) |
| *(separate repo)* `gophersys/photosphere` | **TS + React** | the design system (`@photosphere/*`), consumed as a dependency |

**The one structural gap:** there is no `libs/go/`, but Go is the largest body of code in Helios (the
whole control plane + the build-system engine). Either add a `go/` partition for shared Go libs, or
decide each Go service is an `apps/*` with its own `go.mod` and only truly-shared Go goes in a lib.
Recommended: **add `libs/go/`** — the provider interface, `evidence`, and `agentcfg` are shared by
multiple Go binaries. (Go floor is **1.24**, per the spec-driven corpus correction.)

---

## `libs/protocols/` — Protobuf (buf)

One schema → typed clients on every side. `buf.gen.yaml` generates Go (`connect-go`) into `libs/go/`
and TS (`connect-es`) into `libs/typescript/api`.

| Lib | Purpose | Codegen |
|---|---|---|
| `protocols/helios` | All API + domain messages/services: workspace · identity · provider · broker · templates · policy · audit · gateway · terminal(PTY) streams · `Evidence` | `protoc-gen-go`, `protoc-gen-connect-go`, `protoc-gen-es`, `protoc-gen-connect-es` |

> Transport is **Connect** = gRPC + gRPC-Web + Connect-HTTP-JSON (not "REST"). Split into per-domain
> `.proto` packages as it grows; one buf module.

---

## `libs/typescript/` — TypeScript (strict) + React 19

The client-shared libraries. The design system (`@photosphere/*`) is **not** here — it lives in the
separate `gophersys/photosphere` repo (ADR-0002) and is consumed as a dependency.

| Lib | Purpose | Key deps | Mode |
|---|---|---|---|
| `@helios/domain` | Domain types + pure logic from proto. **No React, no network.** | (generated from `protocols`) | internal |
| `@helios/api` | Connect-ES clients + typed facades — **the only backend seam** | `@connectrpc/connect-web`, `@tanstack/react-query` | internal |
| `@helios/state` | Cross-cutting stores: auth, connection, theme, command-registry | `zustand`, `jotai` | internal |
| `@helios/commands` | The unified command registry → menubar + ⌘K palette + shortcuts + context menus | — | internal |
| `@helios/platform` | **PlatformBridge** ports/adapters (Tauri vs web): keychain, process, tunnel, fs, deep-links | `@tauri-apps/api` | internal |
| `@helios/machines` | XState lifecycle machines (mirror the backend workspace state) | `xstate` | internal |
| `@helios/testing` | Fixtures, fakes, render helpers, Connect/MSW mocks | `msw`, `@testing-library/*` | internal |
| `@helios/tsconfig` / `@helios/biome-config` | Shared dev config presets | — | internal |

> Feature slices (`workspaces`, `secrets`, `infrastructure`, `apps`, `observability`, `settings`) are
> **app modules**, not libs — they live in `apps/frontend`, depend on libs + `@photosphere/*`, never
> on each other.

---

## `libs/go/` — Go 1.24+  *(add this partition)*

Two families. Build the **control plane** for the product; build the **engine** as a deliberate v0.1
slice (one cell first — see the caveat).

### Control plane (the moat)

| Lib | Purpose | Compose / notes |
|---|---|---|
| `workspaceprovider` | **The core interface** + impls: `docker` · `kubernetes` · `vm`(Firecracker/KubeVirt) · `mac`(Orka) · `gpu`. Contract-tested as interchangeable. | study Coder |
| `orchestrator` | Workspace lifecycle reconcile loop (controller pattern: desired vs actual) | — |
| `broker` | Connection/tunnel coordination — WireGuard mesh + DERP relay fallback | compose **Tailscale / tsnet** |
| `identity` | OIDC/SSO, RBAC, orgs/teams | — |
| `templates` | Versioned environment registry (devcontainer-compatible) | — |
| `policy` | Quotas, cost, idle/hibernate, pre-warm pools | — |
| `audit` | Audit log + telemetry | OpenTelemetry |
| `gateway` | The Connect API surface (gRPC + gRPC-Web + Connect-JSON) + PTY/file/port streams | from `protocols` |

### Agent build-system engine (the discipline layer) — 🔶 v0.1, one cell first

Per `spec-driven-implementation-system.md §8`. **Do not build the full DAG/engine/plugins yet** —
ship the linear web/Go cell, prove the loop closes on a non-gameable gate over ~50 tasks, then
generalize.

| Lib | Owns | Notes |
|---|---|---|
| `agentcfg` | Config + routing + the LLM `Call` (bare wire): binds *model + auth* per role (`think`/`default`/`background`); compiles to harness formats (Claude Code, Aider…) | CUE authoring → immutable Go `Resolved` IR; exists in the corpus (`agentcfg-architecture.md`) |
| `evidence` | The `Evidence` **interface** (Claim·Verdict·Confidence·Reproducibility·Cost·Provenance·Staleness·Payload) + impls (`GoTestEvidence`…) | gate reads the envelope only; `Payload` opaque |
| `spec` | `Spec = {Contract, Template-ref, Tests, Gate}` (four roles behind interfaces) | the unit of work |
| `template` | Per-cell scaffolds (a "typed hole" in Go = interface + `panic("unimplemented")` + `_test.go` first) | one cell to start |
| `codingharness` | The implementing loop — own loop on `agentcfg.Client` (parse `tool_use`, dispatch read/edit/run-tests, budget). **The biggest v0.1 item.** | inner/advisory loop |
| `testharness` | Clean-env provision + exercise + emit `Evidence` in a room the coding model never wrote to (anti-reward-hack); later the scarce-resource **leasing** scheduler | = doc-04 Provision+Exercise |
| `engine` | Walks the phase chain; binds phase→model via `agentcfg`; holds the mutable run-state | v0.1 = linear chain, not a DAG |
| `cell` | The typed `Cell` schema (D1–D5 + topology + ports) + the **I1–I9** invariant validator | CUE → Go; reference impl already in `photosphere/.claude/cell.json` |

> `evidence`, `agentcfg`, `cell` are shared by both families and by the control plane's gate — hence
> a real reason for `libs/go/` rather than burying them in one app.

---

## `libs/rust/` — Rust (Tauri v2)

| Lib / crate | Purpose |
|---|---|
| `helios-shell` | The Tauri v2 desktop shell: native menubar, windows, tray, deep links, auto-updater. (Wraps the *same* web bundle the browser serves.) |
| `helios-native` | Capability crates backing `@helios/platform`'s Tauri adapter: OS keychain (`keyring`/stronghold), process spawn, the client-side tunnel, fs. Exposed to the webview as Tauri commands. |

> The **agent** that runs *inside* workspaces is **Go** (static, `CGO_ENABLED=0`), not Rust — see apps.

---

## `libs/python/` — Python  *(future / peripheral)*

Not core to v1. Reserve for: agent-system **eval harnesses** (spec-determinacy + mutation-score
instrumentation), data/ETL, and the model series' **ML/eval cell** (MLflow/DVC) if/when Helios grows
an ML surface. Placeholder until then.

## `libs/zephyr/` — C / Zephyr  *(future)*

The embedded firmware cell (nRF52840 / nRF9161 / ESP32) — explicitly the **last** discipline Helios
will support (doc 04). Placeholder; built when the embedded cell is real (Test Bed via Labgrid).

---

## `apps/` — the deployables (not libraries)

| App | Language | Imports |
|---|---|---|
| `apps/backend` | **Go** | `libs/go/*` — the control-plane modular monolith (`helios up` local + server). Split to services only when scale forces it. |
| `apps/frontend` | **TS + React 19** | `libs/typescript/*` + `@photosphere/*` — one bundle ships as the web app **and** inside the Tauri shell |
| `apps/desktop` | **Rust (Tauri v2)** | `libs/rust/helios-shell` wrapping the frontend bundle |
| `apps/agent` | **Go** | the `helios-agent` (dials out, brokers PTY/files/ports) |

---

## The separate repo — `gophersys/photosphere` (TS + React, **publish** mode)

The design system, its own versioned asset (ADR-0002), consumed by `apps/frontend` as `@photosphere/*`:
`tokens · theme · primitives · recipes · motion · icons · components · patterns · charts · graph`.
Foundation decided by data: **React Aria Components** (ADR-0004) + **vanilla-extract** (ADR-0005) +
Style Dictionary + Motion + Phosphor + uPlot/visx + React Flow.

---

## Build order (critical path)

```
protocols ─┬─▶ libs/go: workspaceprovider ▶ orchestrator ▶ broker ▶ gateway ─▶ apps/backend
           ├─▶ libs/typescript: domain ▶ api ▶ state/commands/platform ─────────▶ apps/frontend ─▶ M0 demo
           └─▶ (photosphere repo): tokens ▶ theme ▶ primitives ▶ components ─────▶ @photosphere/*
apps/desktop (Rust shell) wraps the frontend bundle once it runs.

build-system (parallel, v0.1, ONE cell): agentcfg ▶ evidence+GoTestEvidence ▶ testharness ▶
  codingharness ▶ spec/template ▶ engine(linear)   — prove on ~50 web/Go tasks before generalizing.
```

**M0** (the first product demo) needs only: `protocols` + a thin `workspaceprovider(docker)` + `broker`
+ `gateway` + `apps/agent` + `domain`/`api`/`platform` + `apps/frontend` + the Photosphere walking
skeleton. Everything else is later milestones.

## Conventions (from the existing repo — follow them)

- **project.json + `ctl.sh`** per project; Nx targets wrap `bash ./ctl.sh <cmd>` via `nx:run-commands`.
- **Conventional Commits**; **no AI/LLM attribution** in commits.
- **Nx Cloud disabled** (`neverConnectToCloud`) — keep it.
- **yarn 4** workspaces (`apps/*`, `libs/typescript/*`); add `libs/go/` as a Go workspace (`go.work`).
