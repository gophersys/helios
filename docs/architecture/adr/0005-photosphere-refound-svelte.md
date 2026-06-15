# ADR-0005: Re-found photosphere on Svelte as the same standalone asset

- **Status:** Accepted — **amended by ADR-0024** (the design system is re-homed *in-repo* at
  `libs/typescript/<kebab>`, scope `@eden/*`, not a separate published `gophersys/photosphere`
  repo; the framework-agnostic theming theses retained below are unchanged and are now realized by
  the `@eden/theme` generative engine)
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

> **Amendment (2026-06-14, ADR-0024 D1).** The "same standalone, independently-versioned asset in
> a separate `gophersys/photosphere` repo" home is **superseded**: the design system lives **in this
> monorepo** at `libs/typescript/<kebab>` (npm/code scope `@eden/*`), built through a TS/Svelte
> library-engineering pipeline that mirrors the Go ADR-0020 pipeline. Everything else this ADR
> retains — the runtime theming engine, the DTCG ThemeDoc contract, "stabilize schema, vary values",
> CSS custom properties as the runtime substrate, the mode × density × brand axes, OKLCH generative
> theming with WCAG gates, and the behavior/appearance seam — survives intact and is realized by the
> `@eden/theme` library. The behavior-layer fork this ADR opened (OD-1) is closed by the same ruling
> (Bits-UI-primary hybrid). See ADR-0024 and `docs/research/05-design-foundations.md`.
