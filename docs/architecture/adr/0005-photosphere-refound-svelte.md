# ADR-0005: Re-found photosphere on Svelte as the same standalone asset

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

ADR-0004 re-platforms Eden's UI on Svelte. Photosphere (the design system, `gophersys/photosphere`)
is React-founded in its component layer but its load-bearing theses are framework-agnostic.
Options: re-found photosphere on Svelte; fold the design system into the Eden monorepo
(abandoning photosphere ADR-0002); retire it and start fresh.

## Decision

Photosphere continues as the **same standalone, independently-versioned asset** (photosphere
ADR-0002 reaffirmed), re-founded on Svelte. Retained: the runtime theming engine and all of
photosphere ADR-0003 (DTCG-shaped ThemeDoc, semantic-token contract "stabilize schema, vary
values", CSS custom properties as runtime substrate, cascade-scoped dual-context rendering,
mode × density × brand axes, OKLCH generative theming with WCAG gates, behavior/appearance
seam). Superseded: photosphere ADR-0004 (React Aria) and the React-specific portions of
photosphere ADR-0005; the Svelte behavior layer is selected via a data pass of the same rigor
(OD-1).

## Consequences

- Photosphere remains the reference implementation of connector family F6 (design systems) and
  the proof that user-supplied design systems can satisfy the same contract.
- The behavior/appearance seam translates: behavior = the chosen Svelte headless layer
  (theme-invariant); appearance = tokens + recipes (theme-driven). The token contract is the
  stable boundary, which is precisely why the re-platform is survivable.
- WS4 owns the re-founding; photosphere's own ADR chain records the supersessions on its side,
  citing this ADR.
- Standalone-asset costs (cross-repo coordination, version-bump dance) re-accepted knowingly;
  the published-contract discipline (semver tokens API) is unchanged.
