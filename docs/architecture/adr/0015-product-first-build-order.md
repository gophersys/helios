# ADR-0015: Product-first build order — the UI pulls the architecture

- **Status:** Accepted (amends ADR-0007's sequencing; rules OD-2)
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

ADR-0007 sequenced the build kernel-first (hand-built kernel → libraries → platform). Mateo
ruled a pivot: development begins with the product UI that hosts the product-design process —
the staged, agent-assisted document flow (11) is the product's core experience, and the gap it
bridges between human and machine is where value concentrates. Interfaces, adapters, and
libraries should be *pulled into existence by product need* rather than built bottom-up in
advance. The dogfooding ladder's full self-hosting proof moves further out; this is accepted.
A secondary driver is documented (ADR-0014): documentation accumulation outpaced consumability;
visible product re-anchors the work.

## Decision

1. **The development spine is `apps/frontend`** — SvelteKit + Svelte 5 (this rules OD-2:
   SvelteKit over a bare Vite SPA; the Tauri shell wraps a static-adapter build later) — hosting
   the **document workspace**: the product-design process as a working surface (tiers, statuses,
   document reading, validation/coverage, gates).
2. **Pull-based architecture.** Platform capabilities enter the build when a screen needs them.
   First pull: projection serving — v0 shells the `documentvalidator` CLI from SvelteKit server
   routes; a Go backend slice replaces the shell-out when it hurts (the seam is the projection
   contract, already golden-pinned, so the swap is mechanical).
3. **The ladder (06) is unchanged as the proof framework** — rung exit criteria stand; only the
   order in which work reaches them changes. WS1 contract freezes gate *library
   implementations*, not UI v0.
4. **OD-1 (Svelte behavior layer) is deliberately not ruled.** v0 uses plain Svelte components
   styled by CSS custom-property tokens (consistent with the photosphere theses); the behavior
   layer is selected when component complexity pulls it.

## Consequences

- 09 (build plan) is amended on next touch: the workstream spine becomes UI-first with
  pull-based backlog; milestones M1/M2 remain valid but are no longer the leading edge.
- OD-2 resolved (RD-14). OD-3 partially exercised in practice (Svelte 5 runes; query layer
  pulled when needed).
- The kernel/codingharness/testharness work resumes when the UI's intake-agent surface pulls F4
  — at which point the WS1 freeze becomes blocking again.
- Risk accepted: building UI against a CLI shell-out defers backend design; mitigated by the
  projection contract being the frozen seam (ADR-0011, golden fixtures).
