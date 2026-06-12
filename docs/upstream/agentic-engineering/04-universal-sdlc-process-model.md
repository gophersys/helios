# 04 — The Universal SDLC Model for Helios

**Series:** Agentic Engineering Research — [README](README.md) · builds on [01](01-software-ecology-problems.md)–[03](03-extended-ecosystem-components.md)
**Status:** Complete · **Last updated:** 2026-06-01 · **Reads in:** ~9 min
**Note:** this is the *consolidated* doc. It replaces the 2026-06-01 working trail (model → stress-test → schema → validation), now in [`archive/`](archive/) — kept for the reasoning/corrections record, not for reading. Everything load-bearing is here.
**Legend:** ✅ verified · 🔶 hypothesis (survived a stated test; falsifiable) · ⚠️ corrected (was wrong earlier today) · 🧩 design choice.

---

## 1. The claim

🔶 **A software category = one invariant spine + a parameter vector.** The phase-concerns and the feedback loop are the same for every kind of software; categories differ only in a small set of *parameters*. Stress-tested across ~20 categories (§6): the spine held everywhere; the original "only target/environment/evidence differ" was **too weak** — five things vary, and one category (IaC) bends the topology. This is the hardened form, falsifiable per dimension.

For Helios this matters because Helios's job is to *present and run* this one system for every kind of software a team builds — desktop, web, mobile, embedded, edge — behind one UI.

---

## 2. The invariant spine (the uniform top)

Ten phase-concerns, a DAG with one feedback edge (10→1). A phase may be null-op or fused, but no category needs a *new* one.

| # | Phase | Produces | Port (pluggable) |
|---|---|---|---|
| 1 Specify | Spec | — |
| 2 Author | SourceChange | **`author`** (LLM coding-harness / swarm / human) |
| 3 Build | Artifact +provenance | `builder` |
| 4 Analyze | static Evidence | `static_analyzer` |
| 5 Provision | Environment | **`environment_provider`** ← diverges most |
| 6 Exercise | dynamic Evidence | **`harness`** (the test container — *same across all categories*) |
| 7 Package | ReleaseCandidate | `packager` |
| 8 Gate | Decision +signature | `gate_policy` + `signer` |
| 9 Deliver | DeploymentRecord / Availability | `deployer` |
| 10 Observe | runtime Evidence → feeds 1 | `observer` |

**The one insight worth keeping:** the *consumer* (the test container at phase 6) is identical everywhere; only the `environment_provider` it dials differs — web dials an ephemeral cluster, mobile a device farm, embedded a **Test Bed** (✅ = Labgrid: a host serving boards over gRPC). ✅ all build commands verified (`west build`, `go build`, `xcodebuild`, `docker build`).

---

## 3. The four currencies (process-as-data)

What flows between phases is typed data, so an engine can run it.

**`Evidence`** — the single canonical definition (⚠️ unified here; was duplicated across 3 docs). An *interface + opaque payload*, not a flat schema. Gates read only the envelope:
```
Evidence {
  kind:            sampled-dynamic | exhaustive-formal | static-derived
                 | physical-measurement | subjective-expert | subjective-population
  claim, verdict:  pass | fail | inconclusive        // raw measurements live in payload, thresholded by the gate
  confidence:      deterministic | flaky(p) | sampled | statistical
  reproducibility: deterministic | stochastic | one-shot-physical
  cost_to_reproduce, staleness, provenance
  verifier_provenance                                 // the ruler's own version (LLM-as-judge is fallible)
  selection:       required | advisory                // the "conjunction of booleans" answer
  payload:         <opaque>
}
```
**`EnvironmentRequest`** `{ target, fidelity, scarcity: elastic | leased-exclusive | physical-fixture | queued-fair-share | expendable, brick_risk, deps, isolation, budget }`.
**`Contract`** `{ provides, consumes, semver, compat_range, conformance }` — the seam between components and between a library and its consumers.
**`Process`** — the spine + bindings as a declarative manifest.

---

## 4. The five parameters (what actually varies)

| | Parameter | Values | Why it varies |
|---|---|---|---|
| **D1** | Change arity | code (+data, +seed, +external-model, +constraints, +assets) | ML/games/LLM-apps version more than code; an `external-model` axis you don't own → drift risk |
| **D2a** | Author determinism | deterministic / **stochastic-search** / swarm-parallel | ⚠️ LLM authoring is stochastic (≠ compilation) — this is the seam I got wrong earlier today |
| **D2b** | Build determinism | deterministic-transform / stochastic-search | FPGA place-and-route, ML training aren't bitwise-reproducible |
| **D3** | Evidence kind | the 6 kinds above | formal-∀ ≠ sampled-∃ ≠ subjective; the highest-leverage dimension |
| **D4** | Delivery | reversibility {reversible → forward-only → irreversible} × ownership {first-party / external-binding / federated} | web reversible; firmware/mobile forward-only; smart-contract irreversible; libraries federated (Deliver runs in *consumers'* DAGs) |
| **D5** | Scale (orthogonal) | single / team / org | the model is otherwise *silent* on Bender's tipping point — adds a `reviewer` port, test-impact selection, VCS-scaling, Conway partitioning |

**Topology selector:** `linear-spine` (almost everything) or `reconciliation-loop` (IaC: artifact ≡ environment, Deliver ≡ apply, Observe ≡ re-plan — the one real topology break).

---

## 5. The Cell schema + invariants

A **`Cell`** is the typed category: `{ id, topology, change, author, build, [evidence], delivery, scale, ports }`. The payoff is the **invariants** — they reject a malformed cell at load time, so the stress-test findings become a guard, not a memory:

| # | Reject if… | Catches |
|---|---|---|
| I1 | stochastic build claims bitwise reproducibility | ML/FPGA |
| I2 | **irreversible delivery** lacks a *required* `exhaustive-formal` evidence + designed-in remediation (proxy/pause) | "smart contract gated only by fuzz tests" |
| I3 | external-binding gate has no pending-review state + Gate→Author back-edge | store/console review |
| I4 | federated delivery has no Availability-record + Contract edge to a consumer | libraries |
| I5 | reconciliation-loop keeps a standalone Provision | IaC |
| I6 | an unowned input has no drift-detection in Observe | foundation-model drift |
| I7 | `subjective-population` evidence isn't a distribution + statistical gate (note: `subjective-expert` is exempt — one trusted reviewer) | games "fun" vs a design demo |
| I8 | org-scale uses run-all-tests / unmodeled review throughput | conjunction-of-booleans, review bottleneck |
| I9 | out-of-band-postmortem evidence on a non-expendable env | kernel crash testing |
| I10 | a `required`-evidence gate has no test-power score (mutation testing) where feasible | a *blind gate* — green on a wrong impl |

🧩 Serialize in CUE (constraints = invariants) → compiles to the `agentcfg` Go IR. Engine that consumes a Cell is **deferred** (see §8).

---

## 6. What was tested, and the result

**~20 categories, red-teamed break-by-default.** Verdict: spine topology invariant everywhere; H1 hardened to §1; 5 params + 1 topology break.

| Verdict | Categories |
|---|---|
| HOLDS (native) | web/SaaS, edge/Go, desktop, CLI |
| HOLDS + parameters | mobile, embedded/Zephyr, libraries, ML training, data/ETL, LLM-apps, FPGA, kernels, firmware, HPC, smart contracts, browser extensions, games |
| DEGENERATE (phases collapse to null-op) | docs-as-code |
| **BREAKS topology** | **Infrastructure-as-Code** (→ reconciliation-loop) |
| **BREAKS by silence** | **scale** (→ added as D5) |

**Validated against the two real in-flight builds** (✅ encoded as Cells): the v0.1 web/Go cell and Photosphere's `.claude/` cycle both expressed cleanly — **7 schema refinements, 0 breaks.** Photosphere is a textbook federated/publish cell (I4 fires; its token-contract semver bump *is* the Contract edge to the Helios client).

---

## 7. The Helios cells (parameter vectors)

| Cell | D1 | D2a author | D3 evidence | D4 delivery | topology |
|---|---|---|---|---|---|
| **go-backend (v0.1)** | code (+spec) | **stochastic** (LLM) | sampled-dynamic +mutation-score | reversible · first-party | linear |
| **photosphere** (library) | code + tokens | swarm-parallel | sampled + static + visual + subjective-**expert** | forward-only · **federated** | linear (publish) |
| **helios-app** | code | swarm/human | sampled + subjective-expert (feel) | reversible · first-party | linear (deploy) |
| **zephyr** | code + constraints | deterministic | physical-measurement + formal | forward-only · first-party (Test Bed) | linear |
| *(future)* **ML / LLM** | +data +seed +ext-model | stochastic | statistical + verifier-provenance | reversible | linear |
| *(future)* **IaC** | code | deterministic | static-policy + ephemeral-apply | reconciled | **loop** |

Helios is itself the **LLM-app row** — its foundation model is an unowned input; D3 `verifier_provenance` and D6 drift-detection are its own dogfood.

---

## 8. Scope, cohesion, and honesty

**Load-bearing now:** §2 spine, §4 currencies (esp. Evidence), §7 the `go-backend` and `photosphere` cells. **Validated but ahead of need:** the ~20-category breadth, the FPGA/HPC/smart-contract cells, the IaC topology work — real, but Helios may never build them. **Deferred:** the engine that runs a Cell, recursion/product-altitude, all non-`go-backend` cells.

🧩 **Scope honesty:** this whole model sits *above* the Helios charter's M0–M5 line and leans on the build-farm + test-platform "mountains" the charter defers. It is north-star, not near-term.

**Cohesion with the other threads:**
- ↔ **`helios-spec-driven-system` (the build):** STRONG and reconciled — that thread builds the *deep* v0.1 cell that is one instance of this *wide* frame; they cross-reference; Evidence is now single-sourced here. Clean split: wide frame (here) vs deep build (there).
- ↔ **`helios-project` / Photosphere (UI/UX):** THIN BUT CORRECT — meets at exactly one seam (Photosphere = a publish-mode cell, §7), grounded by the real encoding in §6. Shared root: `HELIOS.md`.

⚠️ **What I got wrong today (so you calibrate trust):** my first drafts over-asserted and were corrected on a second pass — "signal twister" (not a real term), WorkspaceProvider ≡ EnvironmentProvider (overstated → generalization), firmware rollback (backwards → MCUboot auto-reverts), `go-backend` determinism (called it deterministic → it's stochastic-authored), plus minor tooling facts. All fixed in this doc. The pattern is real: trust the ✅-tagged claims; treat 🔶 as ideas, not facts.

---

## 9. Claims ledger (review this, not the prose)

| Claim | Status |
|---|---|
| Spine topology is invariant across software types | 🔶 survived ~20 categories |
| Category = spine + 5-parameter vector | 🔶 the load-bearing idea |
| Consumer (test container) uniform; only environment_provider differs | 🔶 strong |
| Test Bed pattern = Labgrid (compose, don't build) | ✅ |
| Evidence = interface + opaque payload (not one schema) | ⚠️ corrected, now canonical |
| IaC needs a reconciliation-loop topology | 🔶 one known instance |
| Scale (D5) is orthogonal and was missing | ⚠️ added |
| go-backend authoring is stochastic, not deterministic | ⚠️ corrected |
| Photosphere is a federated publish cell | ✅ encoded |
| Go 1.26 / Nordic+Espressif / k8s+Helm+Argo facts | ✅ verified |
| The engine, recursion, non-go cells | 🔶 deferred — not built |

---

## 10. The next step

Stop designing the frame — three validation rounds converged with zero breaks, and the cell on your critical path round-trips. **The next real information is empirical, in the `helios-spec-driven-system` thread:** build the v0.1 web/Go loop, run ~50 tasks, read the spec-determinacy-variance × mutation-score table. That confirms or kills the load-bearing hypotheses. Don't grow this doc further.

**Sources / trail:** [`archive/`](archive/) holds the 2026-06-01 working docs (04a stress-test, 04b schema, 04c validation) with full per-category detail and the verification logs. Tooling facts verified against Zephyr/MCUboot, Nordic/Espressif, Go, Kubernetes/Helm/Argo, Labgrid (2026-06-01).
