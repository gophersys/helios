# ADR-0007: Kernel-first bootstrap ladder

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

The dogfooding mandate (T5): Eden must develop itself. Options: kernel-first ladder (hand-build
the minimal build-system kernel, then every rung builds the next); two parallel tracks (product
conventionally, kernel separately, merge later); platform-first with dogfooding deferred.
The system cannot bootstrap from zero — a strong model cannot author the harness that runs it
(spec-driven §8's premise, accepted here 🔶) — so some hand-built kernel exists under every
option; the question is whether the rest of the platform is built by it or merely after it.

## Decision

Adopt the **kernel-first ladder** L0–L4 as specified in 06: hand-built kernel (L0) →
kernel builds the libraries through ~50 gated tasks (L1, build-system invariant I11) → kernel builds
the platform, eden repo becomes project #1 (L2) → Eden maintains Eden with self-migration N→N+1
(L3) → generalization to the second cell, archetypes, wizard (L4).

## Consequences

- The build plan and the dogfooding proof are the same artifact — no separate "migration to our
  own platform" project later.
- Velocity cost at L0/L1 accepted: product surface arrives at L2, later than a conventional
  build would deliver it — paid back by L1's run data calibrating cost models (B4/T6) and by the
  kernel being exercised on real work from its first week.
- Scope guard inherited: no engine DAG, recursion, or additional cells before L1 closes (I11).
- Parallel workstreams within rungs (09 §2) are the idle-time answer; parallel *rungs* are not.
