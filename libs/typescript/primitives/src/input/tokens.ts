/**
 * `@eden/primitives` — Input token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. This module is the ONLY place the Input's appearance is decided, and it
 * decides NOTHING by hand: every color, size, and space is READ OUT of a generated {@link Theme}
 * from `@eden/theme`. The component markup (`input.svelte` / consumed by `textarea.svelte`) binds
 * the CSS custom properties this module emits — it carries no literal color or px.
 *
 * A text field is a typed surface, so the role selection is: `onSurface` text over the `surface`
 * fill, bordered by `outline` at rest and by `error` when invalid. Both foreground/background pairs
 * (text-over-surface, AND border-over-surface for the focus/error ring visibility) are recomputed in
 * `input.design.test.ts` against @eden/theme's contrast gate, so "looks legible" is a passing gate.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';

/** The CSS-variable namespace every Input custom property carries (one prefix, derived names). */
const VAR_PREFIX = '--eden-input';

/**
 * The resolved token set an Input/Textarea instance renders from. Every field is a CSS value DERIVED
 * from a generated {@link Theme}. The raw OKLCH values ride alongside (the `*Oklch` fields) so the
 * design-correctness gate can recompute the contrast ratio from the SAME numbers the CSS carries.
 */
export interface InputTokens {
  /** The text (and caret) color as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly foreground: string;
  /** The field fill color as a CSS `oklch(...)` string — the `surface` role. */
  readonly background: string;
  /** The resting border color as a CSS `oklch(...)` string — the `outline` role. */
  readonly border: string;
  /** The invalid-state border/ring color as a CSS `oklch(...)` string — the `error` role. */
  readonly borderInvalid: string;
  /** The placeholder color as a CSS `oklch(...)` string — the `outline` role (muted, gate-checked). */
  readonly placeholder: string;
  /** The raw OKLCH of the text foreground — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the field background — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The raw OKLCH of the resting border — checked for visibility against the surface. */
  readonly borderOklch: OkLch;
  /** The raw OKLCH of the invalid border — checked for visibility against the surface. */
  readonly borderInvalidOklch: OkLch;
  /** The raw OKLCH of the placeholder — checked against the field background. */
  readonly placeholderOklch: OkLch;
  /** The minimum hit target, px — the decoupled AAA tap area (theme.controlGeometry.hitTargetPx). */
  readonly hitTargetPx: number;
  /** The visual field height, px (theme.controlGeometry.componentHeightPx — on the 4px grid). */
  readonly heightPx: number;
  /** The horizontal padding, px — the theme vertical inset (a scale value, not eyeballed). */
  readonly paddingInlinePx: number;
  /** The vertical inset, px (theme.controlGeometry.insetPx — on the 4px grid). */
  readonly paddingBlockPx: number;
  /** The font size, px — INVARIANT under density (theme.controlGeometry.fontSizePx). */
  readonly fontSizePx: number;
  /** The line height, px (theme.controlGeometry.lineHeightPx). */
  readonly lineHeightPx: number;
  /** The text font family — the theme's `body` typography role family (the seed's text font). */
  readonly fontFamily: string;
}

/** The text font family is the theme's `body` typography role family (the seed's text font). */
function bodyFontFamily(theme: Theme): string {
  const body = theme.typography.find((t) => t.name === 'body') ?? theme.typography[0];
  return body ? body.fontFamily : 'inherit';
}

/**
 * Derive the full {@link InputTokens} from a generated theme. PURE: no globals, no I/O — the theme
 * is the single input (the New(configuration) spine). `deriveInputTokens` is the function the
 * design-correctness gate audits and the Input/Textarea components render from.
 */
export function deriveInputTokens(theme: Theme): InputTokens {
  const roles = theme.roles;
  const g = theme.controlGeometry;
  return {
    foreground: oklchToCss(roles.onSurface.value),
    background: oklchToCss(roles.surface.value),
    border: oklchToCss(roles.outline.value),
    borderInvalid: oklchToCss(roles.error.value),
    placeholder: oklchToCss(roles.outline.value),
    foregroundOklch: roles.onSurface.value,
    backgroundOklch: roles.surface.value,
    borderOklch: roles.outline.value,
    borderInvalidOklch: roles.error.value,
    placeholderOklch: roles.outline.value,
    hitTargetPx: g.hitTargetPx,
    heightPx: g.componentHeightPx,
    // The horizontal padding is the vertical inset (a single scale step) — symmetric inset for a
    // text field reads cleaner than the 2:1 button ratio; it is a SCALE value, never hand-set.
    paddingInlinePx: g.insetPx,
    paddingBlockPx: g.insetPx,
    fontSizePx: g.fontSizePx,
    lineHeightPx: g.lineHeightPx,
    fontFamily: bodyFontFamily(theme),
  };
}

/**
 * Render an {@link InputTokens} as the inline `style` custom-property string the component binds.
 * Every entry is an `--eden-input-*` var whose VALUE is a derived token — the markup references
 * `var(--eden-input-*)` only and carries no literal (the provenance lint passes by construction).
 */
export function inputStyleVars(tokens: InputTokens): string {
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-fg`, tokens.foreground],
    [`${VAR_PREFIX}-bg`, tokens.background],
    [`${VAR_PREFIX}-border`, tokens.border],
    [`${VAR_PREFIX}-border-invalid`, tokens.borderInvalid],
    [`${VAR_PREFIX}-placeholder`, tokens.placeholder],
    [`${VAR_PREFIX}-hit-target`, `${String(tokens.hitTargetPx)}px`],
    [`${VAR_PREFIX}-height`, `${String(tokens.heightPx)}px`],
    [`${VAR_PREFIX}-padding-inline`, `${String(tokens.paddingInlinePx)}px`],
    [`${VAR_PREFIX}-padding-block`, `${String(tokens.paddingBlockPx)}px`],
    [`${VAR_PREFIX}-font-size`, `${String(tokens.fontSizePx)}px`],
    [`${VAR_PREFIX}-line-height`, `${String(tokens.lineHeightPx)}px`],
    [`${VAR_PREFIX}-font-family`, tokens.fontFamily],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}
