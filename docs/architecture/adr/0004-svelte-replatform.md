# ADR-0004: Re-platform the UI on Svelte

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

The corpus made data-driven UI decisions on React 19: React Aria Components as behavior layer
(photosphere ADR-0004), vanilla-extract as styling/token layer (photosphere ADR-0005), and a
React-shaped `@helios/*` client-library plan (the former `/LIBRARIES.md`, now in `docs/attic/`:
zustand/jotai, XState, TanStack
Query, Connect-ES). Mateo ruled a deliberate re-platform: Eden's UI discipline is **Svelte**.
This is a value-ruling that supersedes settled decisions — recorded with its full blast radius
rather than absorbed silently.

## Decision

Eden's platform UI (`apps/frontend`) and the v1 UI cell (`svelte-ui`) are **Svelte (Svelte 5)**.
One bundle ships as the web app and inside the Tauri shell (`apps/desktop`), unchanged in shape.
The design system is re-founded on Svelte while keeping its framework-agnostic core (ADR-0005).

## Consequences

- **Supersedes** photosphere ADR-0004 (React Aria) and the React-specific halves of photosphere
  ADR-0005;
  the theming-engine theses of photosphere ADR-0003 (themes-as-data, DTCG ThemeDoc, runtime CSS
  custom properties, cascade-scoped dual-context, OKLCH generative theming) are
  framework-agnostic and **survive intact**.
- The original `libs/typescript` plan is invalid where React-specific (10 §12 carries the
  Svelte-shaped manifest); replacements tracked
  as OD-1 (behavior layer), OD-2 (SvelteKit vs SPA), OD-3 (state/query). Framework-agnostic
  picks survive: Connect-ES clients, vanilla-extract remains a candidate (build-time, no React
  dependency) pending the OD-1 data pass.
- Accepted costs: thinner LLM training data for Svelte 5 runes than React (mitigation: knowledge
  rules + pinned docs, P7); re-founding work in photosphere (WS4); loss of the React Aria a11y
  matrix — the OD-1 selection must produce an a11y evidence story before the `svelte-ui` cell
  ships.
- The `svelte-ui` cell becomes the second cell through the kernel (L4); its archetype carries
  the blessed Svelte stack.
