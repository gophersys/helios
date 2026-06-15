/**
 * `@eden/primitives` — the chat-surface token vocabulary (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH, and ONE CONCEPT ONE HOME (10 §9). Every chat surface — a message bubble,
 * a tool-call card, a permission prompt, a usage meter, a thinking block — is a small set of the
 * SAME primitives: a coloured CONTAINER (a `{ fg, bg, border }` triple drawn from the theme's
 * semantic roles, every text/background pair carrying the contrast guarantee by construction) and a
 * PROPORTION pick (a font size + line height from the generated type scale, a space from the
 * generated spacing ramp). This module is the single place those primitives are derived; every chat
 * component's `tokens.ts` CITES these helpers and never re-spells a role selection or a px.
 *
 * Nothing here is decided by hand: a {@link SurfacePair} reads a role's OKLCH out of a generated
 * {@link Theme} (`generateTheme(seed)`), and the raw OKLCH rides alongside the `oklch(...)` CSS
 * string so the design-correctness gate recomputes the contrast ratio from the SAME numbers the CSS
 * carries (the proof audits the emitted value, never a copy). A proportion pick reads a real
 * typography role and a real spacing-ramp step — so "on the scale" is a property of the value, not a
 * comment. The role pairs chosen here are exactly the gated pairs @eden/theme resolves through the
 * WCAG contrast gate (`on-*` foregrounds over their fills, and the state/role colours as text over
 * the surface — every one clears AA 4.5 in both modes, asserted in `chat-surface.design.test.ts`).
 */

import { oklchToCss, type Theme, type OkLch, type TypographyRole } from '@eden/theme';

/**
 * A resolved CONTAINER: a foreground/background/border triple, each an `oklch(...)` CSS string, with
 * the raw OKLCH of the text/fill pair kept alongside so the contrast gate recomputes the ratio from
 * the emitted numbers. This is the atom every chat container (bubble / card / block) is built from.
 */
export interface SurfacePair {
  /** The foreground (text/icon) colour as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The background (fill) colour as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The border colour as a CSS `oklch(...)` string (equals the background when the edge is flush). */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio from THIS. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the background — the contrast gate recomputes the ratio from THIS. */
  readonly backgroundOklch: OkLch;
}

/** Build a {@link SurfacePair} from a `{ fg, bg, border }` OKLCH selection (the one derivation seam). */
function pairFrom(fg: OkLch, bg: OkLch, border: OkLch): SurfacePair {
  return {
    foreground: oklchToCss(fg),
    background: oklchToCss(bg),
    border: oklchToCss(border),
    foregroundOklch: fg,
    backgroundOklch: bg,
  };
}

/**
 * The PROSE container: `on-surface` text over the `surface` fill, outlined by the `outline` role.
 * This is the reading default for every chat surface (the assistant prose, a card body, a meter
 * label) — the highest-contrast pair the theme resolves (≈19:1 light / ≈15:1 dark).
 */
export function proseSurface(theme: Theme): SurfacePair {
  const r = theme.roles;
  return pairFrom(r.onSurface.value, r.surface.value, r.outline.value);
}

/**
 * The ACCENT container: `on-primary` text over the `primary` fill (the gated brand pair). Used where
 * a surface must read as the user's own contribution (the user message bubble) — a filled accent.
 */
export function accentSurface(theme: Theme): SurfacePair {
  const r = theme.roles;
  return pairFrom(r.onPrimary.value, r.primary.value, r.primary.value);
}

/**
 * The QUIET container: `on-primary-container` text over the `primary-container` fill (the theme's
 * tonal container pair). A softer, lower-energy filled surface than {@link accentSurface} — used for
 * the assistant bubble and for grouped cards that should recede from the prose without losing the
 * contrast guarantee (`on-*` over its container clears AA by construction).
 */
export function quietSurface(theme: Theme): SurfacePair {
  const r = theme.roles;
  return pairFrom(
    r.onPrimaryContainer.value,
    r.primaryContainer.value,
    r.onPrimaryContainer.value,
  );
}

/**
 * A STATE container drawn as TEXT over the prose surface: the named state role (`error` / `success` /
 * `warning` / `info`) as the foreground, the `surface` as the background, the same state colour as
 * the edge. The state colours are bare fills in the theme (no paired `on-*`), so the correct, gated
 * way to surface them is as text/iconography over the reading surface — every one clears AA 4.5 over
 * the surface in both modes (asserted in the design lane). This is how a permission prompt signals
 * "destructive", a tool card signals "failed", a usage meter signals "over budget".
 */
export type StateRole = 'error' | 'success' | 'warning' | 'info';

export function stateSurface(state: StateRole, theme: Theme): SurfacePair {
  const r = theme.roles;
  const fill = r.surface.value;
  const accent =
    state === 'error'
      ? r.error.value
      : state === 'success'
        ? r.success.value
        : state === 'warning'
          ? r.warning.value
          : r.info.value;
  return pairFrom(accent, fill, accent);
}

/**
 * A resolved PROPORTION: a font size + line height (both px) read out of a generated typography role,
 * plus that role's family. The chat components size their text from these picks (never a hand px).
 */
export interface ProportionPick {
  /** The font size, px — the typography role's generated `size = base·ratio^i` (research §B.1). */
  readonly fontSizePx: number;
  /** The line height, px — the role's generated line-height (WCAG 1.4.12 floor applied upstream). */
  readonly lineHeightPx: number;
  /** The role's font family (the seed's text or display font). */
  readonly fontFamily: string;
}

/**
 * Find a typography role by name, falling back to `body` then the FIRST generated role. Returns
 * `undefined` only if the typography list is empty (which a generated theme never produces — the
 * `body` role is always present at index 0, research B1 ladder); the caller handles that case so the
 * derivation is total without a non-null assertion.
 */
function roleByName(theme: Theme, name: string): TypographyRole | undefined {
  return (
    theme.typography.find((r) => r.name === name) ??
    theme.typography.find((r) => r.name === 'body') ??
    theme.typography[0]
  );
}

/**
 * Resolve a {@link ProportionPick} for a named typography role (e.g. `body`, `label`, `caption`,
 * `title`). The line height is the role's `lineHeight` multiple × its `fontSizePx`, rounded to a
 * whole pixel — a derived value on the type scale, never eyeballed. If a theme carried no typography
 * at all (never the case for a generated theme), the pick falls back to a 0-size `inherit` so the
 * function stays total — the same totality contract the Button's `bodyFontFamily` keeps.
 */
export function proportion(theme: Theme, role: string): ProportionPick {
  const r = roleByName(theme, role);
  if (!r) return { fontSizePx: 0, lineHeightPx: 0, fontFamily: 'inherit' };
  return {
    fontSizePx: r.fontSizePx,
    lineHeightPx: Math.round(r.fontSizePx * r.lineHeight),
    fontFamily: r.fontFamily,
  };
}

/**
 * The set of px values on the generated spacing ramp — the membership oracle the design lane asserts
 * every chat space against (`expect(rampPx(theme)).toContain(value)`), and the source the `space`
 * pick draws from. The ramp is brand-invariant (research §B.2): `2, 4, 8, 12, 16, 20, 24, …`.
 */
export function rampPx(theme: Theme): readonly number[] {
  return theme.spacing.map((s) => s.px);
}

/**
 * Pick the spacing-ramp step at a given INDEX (0-based into the generated ramp). A chat component
 * names its paddings/gaps by ramp index, so every space it renders is provably a ramp step — picking
 * `space(theme, 4)` yields `16px` for the default ramp, `space(theme, 6)` yields `24px`. The index is
 * clamped into range so the pick is total for any ramp length.
 */
export function space(theme: Theme, index: number): number {
  const ramp = theme.spacing;
  const i = Math.max(0, Math.min(index, ramp.length - 1));
  const step = ramp[i];
  // The clamp keeps `i` in range for any non-empty ramp; an empty ramp (never generated) yields 0,
  // keeping the pick total without a non-null assertion.
  return step ? step.px : 0;
}

/**
 * The decoupled AAA hit-target floor (px) for the active theme — the SAME value the Button guarantees
 * (`theme.controlGeometry.hitTargetPx`, clamped to ≥44 for the touch context). Every interactive
 * chat target (a permission action, a thinking-block toggle) sizes its min tap area from this, so a
 * dense visual box never shrinks the accessible target (I1/I2, ADR-0024).
 */
export function hitTargetPx(theme: Theme): number {
  return theme.controlGeometry.hitTargetPx;
}

/**
 * Render a list of `[suffix, cssValue]` pairs as an inline `style` custom-property string under a
 * component's variable prefix — the seam that keeps every *.svelte free of literals (it references
 * `var(${prefix}-${suffix})` only). A colour value is passed through verbatim (already `oklch(...)`);
 * a numeric value is suffixed `px`; a string value (a font family, a generic keyword) is passed
 * through. This is the ONE emitter the chat components share — one concept, one home.
 */
export type StyleEntry = readonly [suffix: string, value: string | number];

export function styleVars(prefix: string, entries: readonly StyleEntry[]): string {
  return entries
    .map(([suffix, value]) => {
      const css = typeof value === 'number' ? `${String(value)}px` : value;
      return `${prefix}-${suffix}: ${css};`;
    })
    .join(' ');
}
