# 00 — Eden Charter

> Status: Draft · 2026-06-12 · Canonical home for: what Eden is, theses T1–T8, scope, non-goals.

## 1. What Eden is

Eden is an **opinionated platform for building and operating software systems with agentic
engineering**. A user describes a system; Eden instantiates a monorepo from typed archetypes,
drives schema-gated agent pipelines to implement it, provisions and operates the infrastructure
behind provider adapters, and keeps the whole thing observable, billable, and maintainable — from
prototype (Docker, local) to production (Kubernetes, any cloud) — for both technical and
non-technical operators.

The interface is low-code/no-code (wizard, visual editor, dashboards, in-app assistants); the
output is full-code (a real monorepo the user owns, openable in a browser editor or local VS Code
at any time). Eden is not a code generator with a UI; it is the **discipline layer** — process,
contracts, evidence, and observability — packaged as a product.

## 2. Why now

✅ Frontier coding models sit within ~1 percentage point of each other on SWE-Bench Verified
(corpus doc 00); the corpus's central thesis — differentiation has moved from the model layer to
the **discipline layer** — follows from it 🔶. Bender's catalogue (corpus doc 01) names fifteen
specific ways current engineering practice breaks at 10× code velocity: quadratic test-compute,
review bottlenecks, multi-agent edit wars, releases outrunning detection, convention drift,
load-bearing token engines. Eden's bet 🔶: the winner is not a better agent but the **system that
makes agent output safe at scale** — Bender's four prescribed investments (capacity visibility,
validation strategy, isolation, abstraction) built as a product rather than adopted as advice.

## 3. Theses

| # | Thesis | Consequence |
|---|---|---|
| T1 | **Contracts over integrations.** Eden defines requirement contracts (ports); adapters satisfy them per provider. | Adding a provider is additive work, never architectural work (05). |
| T2 | **The SDLC is the product.** A typed artifact pipeline with hard schemas at every phase; agents are transform functions; the platform is the type-checker and orchestrator. | "Process baked into code" — corpus doc 04's spine, instantiated (04). |
| T3 | **Evidence-gated autonomy.** Nothing promotes on agent say-so; gates read evidence envelopes produced in clean rooms. | Kills the master-agent-monitor role; humans do up-front specification and gate rulings only (E6). |
| T4 | **Opinionation is the feature.** One blessed library set, one naming standard, one process per cell. | Shrinks agent output space; makes generated systems uniform, reviewable, observable by construction. |
| T5 | **Eden builds Eden.** The platform's complexity proof is self-hosting: version N builds, deploys, and migrates to version N+1. | Migration, updates, and observability are core subsystems, not features (06). |
| T6 | **Token and cost predictability.** Every run is metered (tokens, provider spend) from run 1; archetype cost models come from accumulated run data. | Pre-run estimates, budgets, and cost ceilings are first-class (04 §6, S9). |
| T7 | **Surprise through thoroughness.** Out-of-band changes (a push straight to GitHub, a console edit in AWS) are detected, flagged, and offered remediation — not silently broken or absorbed. | Drift detection is a contract obligation of every connector family (05 §5, E4). |
| T8 | **Long-term software, not demos.** Generated systems carry tests, telemetry, dashboards, and upgrade paths from their first commit. | The non-technical view (uptime, cost, deploys, incidents) falls out of instrumented-by-default libraries. |

## 4. The user workflow (product spine)

1. **Create project** — wizard: *what kind of system?* → selects archetypes (technology stacks as
   pluggable modules, addable/removable later via a defined **graft** operation, 02); *what design
   system?* → pick a default, generate one, or upload one (DTCG theme + component manifest).
2. **Specify** — requirements are extracted into schema-validated artifacts; the user's job is
   up-front intent, not supervision (T3).
3. **Build** — the process engine fans agent swarms over independent artifacts; progress, cost,
   and transcripts stream to the dashboard; in-app assistants answer questions about the run.
4. **Operate** — one view: deploys, health, incidents, provider usage and billing, token spend.
   Drift events surface with remediation options.
5. **Evolve** — new features re-enter at step 2; platform upgrades migrate the project forward;
   the monorepo stays openable in VS Code or the browser editor at every point.

## 5. Scope

**v1 cells:** `go-backend` (Go cloud backend) and `svelte-ui` (Svelte web UI, ADR-0004) — the two
cells defined in 02 §2. The go-backend archetype produces **Connect** services: one service
definition serves gRPC, gRPC-Web, and HTTP/JSON, so the "HTTP backend" and "gRPC backend" service
types are one archetype, not two. The Tauri desktop shell is a platform app wrapping the same
Svelte bundle (ADR-0006) — a delivery wrapper, not a cell.

**v1 substrates:** the substrate enum has four values from day 1 (`docker-compose · kubernetes ·
bare-host · vm`, 02 §1); v1 ships **two adapters** — docker-compose (platform-local) and
kubernetes (k3d/kind locally; managed-cloud adapters EKS/GKE/AKS/DO follow per 05 F1).
**v1 posture:** hosted-default with local-as-a-cluster (ADR-0012, amending ADR-0006) — clients
are control surfaces; compute always runs on a cluster the user points at: the Eden-operated
central metered cluster by default, a local k3d/kind cluster (free, offline, the dogfooding
home), or their own (BYO strongly encouraged). In byo-authority mode (ADR-0013) projects and
repos live entirely with the user; Eden holds organizational metadata only.

**Later cells (catalogued, not built):** mobile, embedded/Zephyr (explicitly last), ML/LLM, IaC
(reconciliation topology). Hardware is "just another substrate adapter" (bare-host/Test Bed) —
the abstraction already covers it, so deferral adds no design debt 🔶.

## 6. Non-goals (v1)

- **Hosted-tier billing/charging.** The central cluster is multi-tenant and metered from v1
  (ADR-0012); charging customers (Stripe/F3) is deferred (OD-6).
- **BYO existing repositories.** The adoption pipeline (analyze → map to archetypes → graft
  libraries incrementally) is deliberately deferred, but three constraints are binding now so the
  door stays open: ① `graft` must not assume Eden-created scaffolding (it is defined over any
  monorepo, 02 §2); ② a git-history **import path** into Eden's authoritative git must remain
  possible (interacts with OD-5, BYO-GitHub-as-authority); ③ archetype mapping must tolerate
  foreign layouts rather than require Eden's. Violating any of these forecloses BYO and requires
  an ADR.
- **Marketplace / third-party connector ecosystem.** Conformance suites (05 §6) are the enabler;
  the ecosystem itself comes after the platform proves itself on itself.
- **Supporting every provider out of the box.** Eden defines its requirements; adapters are added
  as needed (T1). Capability manifests make partial support degrade gracefully, never break.

## 7. Naming

The system is **Eden**, fully and everywhere (ADR-0002). GitHub org stays `gophersys`; the
monorepo becomes `gophersys/eden`; the npm scope becomes `@eden/*`; Go module roots are
`github.com/gophersys/eden/...` (apps) and `github.com/gophersys/libs/go/<library>` (libraries).
The design system remains **photosphere** (its own asset, ADR-0005).
