# ADR-0012: Hosted-default compute; clients are control surfaces; local is just another cluster

- **Status:** Accepted (amends ADR-0006)
- **Date:** 2026-06-12
- **Deciders:** Mateo (intake C3–C7, C19)

## Context

ADR-0006 ruled local-first (`eden up` on the user's machine). The founder intake sharpened the
product reality: the primary persona (C1) will not operate infrastructure; "set it and forget
it" must exist; and the client experience should be identical regardless of where compute lives.
Alternatives considered: keep local-first default (slower path to "it just works" for the
persona that matters); hosted-only (kills offline, free local PoCs, and the dogfooding home).

## Decision

1. **Clients are control surfaces.** The web and desktop apps never run project compute; all
   workloads — agent pods, remote VS Code workspaces, CI runners, deployed PoCs — run on a
   **cluster the user points at** (C4–C5).
2. **Hosted-default.** The default cluster is the Eden-operated central multi-tenant kubernetes
   cluster, metered and charged (C3, C6). It is **an ordinary F1 adapter instance with zero
   special code paths** — it must pass the same conformance suite as every BYO cluster (T1/E1).
3. **Local is just another cluster.** A local k3d/kind cluster is fully supported as a cluster
   the user points at: free PoCs, offline development, and the home of Eden's own L0–L2
   dogfooding (C19).
4. **BYO strongly encouraged** in product posture: connect any conformant kubernetes (k3s, EKS,
   GKE, AKS, DO, …) or cloud (C7, C15). Conformance + capability manifests (05 §3/§6) are what
   "anything from k3s to EKS works" means mechanically.

## Consequences

- ADR-0006 is amended: "local-first" becomes "hosted-default with local-as-a-cluster"; the
  projects-live-with-the-user property is preserved in BYO mode and by data-minimization
  (ADR-0013).
- Tenancy isolation and metering on the central cluster move earlier on the roadmap (07 §6,
  S9); namespace-per-project + quota policy become F1 contract obligations for the multi-tenant
  adapter.
- kubernetes-class clusters become the primary user-workload substrate; docker-compose remains
  for platform self-hosting and degenerate local cases 🧩.
- Deployment **fleets** (C17: per-customer isolated environments with gated rollouts) ride this
  posture; fleet architecture is tracked as OD-13.
