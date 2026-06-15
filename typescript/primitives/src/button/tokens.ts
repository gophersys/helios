/**
 * `@eden/primitives` — Button token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. This module is the ONLY place the Button's appearance is decided, and
 * it decides NOTHING by hand: every color, size, and space is READ OUT of a generated
 * {@link Theme} from `@eden/theme` (`generateTheme(seed)`), never pasted. The component markup
 * (`button.svelte`) consumes the CSS custom properties this module emits — it carries no literal
 * color or px. That is what makes the design-correctness gate mechanical: the contrast of the
 * `fg`/`bg` pair, the 44px hit-target floor, and the scale-provenance of every size are PROPERTIES
 * of the values this function returns, asserted in `button.design.test.ts`.
 *
 * The variant→role mapping is the ONE design decision here, and it is a mapping onto the theme's
 * semantic roles (primary / surface+outline / surface), not onto colors. The roles already carry
 * the contrast guarantee (`@eden/theme` resolves every `on-*` foreground through the contrast gate
 * by construction); this module merely SELECTS the role pair per variant.
 */

import {
  generateTheme,
  oklchToCss,
  C21_SEED,
  type Theme,
  type ThemeSeed,
  type GenerateOptions,
  type OkLch,
} from '@eden/theme';

/** The Button visual variants — each is a SELECTION of a theme role pair, never a color. */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

/** The CSS-variable namespace every Button custom property carries (one prefix, derived names). */
const VAR_PREFIX = '--eden-button';

/**
 * The resolved token set a Button instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme} — an `oklch(...)` string for a color, a `<n>px` string for a dimension.
 * The raw OKLCH / numeric values are kept alongside (the `*Oklch` / `*Px` fields) so the
 * design-correctness gate can recompute the contrast ratio and check the scale provenance from the
 * SAME numbers the CSS carries (the proof is honest — it audits the emitted value, not a copy).
 */
export interface ButtonTokens {
  /** The foreground (text/icon) color as a CSS `oklch(...)` string. */
  readonly foreground: string;
  /** The background (fill) color as a CSS `oklch(...)` string. */
  readonly background: string;
  /** The border color as a CSS `oklch(...)` string (equals `background` for filled variants). */
  readonly border: string;
  /** The raw OKLCH of the foreground — the contrast gate recomputes the ratio from this. */
  readonly foregroundOklch: OkLch;
  /** The raw OKLCH of the background — the contrast gate recomputes the ratio from this. */
  readonly backgroundOklch: OkLch;
  /** The minimum hit target, px — the decoupled AAA tap area (theme.controlGeometry.hitTargetPx). */
  readonly hitTargetPx: number;
  /** The visual component height, px (theme.controlGeometry.componentHeightPx — on the 4px grid). */
  readonly heightPx: number;
  /** The horizontal padding, px — derived from the theme spacing ramp (a scale value, not eyeballed). */
  readonly paddingInlinePx: number;
  /** The vertical inset, px (theme.controlGeometry.insetPx — on the 4px grid). */
  readonly paddingBlockPx: number;
  /** The icon/label gap, px (theme.controlGeometry.gapPx). */
  readonly gapPx: number;
  /** The font size, px — INVARIANT under density (theme.controlGeometry.fontSizePx). */
  readonly fontSizePx: number;
  /** The line height, px (theme.controlGeometry.lineHeightPx — WCAG 1.4.12 floor applied upstream). */
  readonly lineHeightPx: number;
  /** The text font family — the theme's `body` typography role family (the seed's text font). */
  readonly fontFamily: string;
}

/** Map a variant to its `{ fg, bg, border }` role selection out of the generated theme. */
function rolePairFor(
  variant: ButtonVariant,
  theme: Theme,
): {
  fg: OkLch;
  bg: OkLch;
  border: OkLch;
} {
  const roles = theme.roles;
  switch (variant) {
    case 'primary':
      // Filled: on-primary text over the primary fill (the theme's gated foreground pair).
      return { fg: roles.onPrimary.value, bg: roles.primary.value, border: roles.primary.value };
    case 'secondary':
      // Outlined: on-surface text over the surface, bordered by the outline role.
      return { fg: roles.onSurface.value, bg: roles.surface.value, border: roles.outline.value };
    case 'ghost':
      // Text-only: on-surface text over the surface; the border is the surface (invisible at rest).
      return { fg: roles.onSurface.value, bg: roles.surface.value, border: roles.surface.value };
    case 'danger':
      // Filled-destructive: on-error text over the error fill (the theme's gated foreground pair).
      // The `error` role and its `on-error` foreground already carry the contrast guarantee by
      // construction (@eden/theme resolves every on-* through the contrast gate) — this SELECTS them.
      return { fg: roles.onError.value, bg: roles.error.value, border: roles.error.value };
  }
}

/**
 * The horizontal padding is DERIVED as twice the vertical inset: a button reads wider than it is
 * tall (the 2:1 inline:block ratio the research B2 ramp provides as adjacent steps), so the value
 * is a SCALE value, never a hand-set number. That `insetPx * 2` lands on a real spacing-ramp step
 * for every density is a PROPERTY of the ramp asserted in `button.design.test.ts`
 * (`expect(rampValues).toContain(t.paddingInlinePx)`) — verified by test, not branched on in code
 * (a branch whose two arms return the same number is an equivalent-mutant trap, not real logic).
 */
function inlinePaddingPx(theme: Theme): number {
  return theme.controlGeometry.insetPx * 2;
}

/** The text font family is the theme's `body` typography role family (the seed's text font). */
function bodyFontFamily(theme: Theme): string {
  const body = theme.typography.find((t) => t.name === 'body') ?? theme.typography[0];
  // The `body` role is always generated (research B1 ladder, index 0); the fallback keeps the
  // function total if a future seed reshaped the ladder (`inherit` is a valid CSS font-family).
  return body ? body.fontFamily : 'inherit';
}

/**
 * Derive the full {@link ButtonTokens} for a variant from a generated theme. PURE: no globals, no
 * I/O — the theme is the single input (the New(configuration) spine, rule 10). `deriveButtonTokens`
 * is the function the design-correctness gate audits and the component renders from.
 */
export function deriveButtonTokens(variant: ButtonVariant, theme: Theme): ButtonTokens {
  const { fg, bg, border } = rolePairFor(variant, theme);
  const g = theme.controlGeometry;
  return {
    foreground: oklchToCss(fg),
    background: oklchToCss(bg),
    border: oklchToCss(border),
    foregroundOklch: fg,
    backgroundOklch: bg,
    hitTargetPx: g.hitTargetPx,
    heightPx: g.componentHeightPx,
    paddingInlinePx: inlinePaddingPx(theme),
    paddingBlockPx: g.insetPx,
    gapPx: g.gapPx,
    fontSizePx: g.fontSizePx,
    lineHeightPx: g.lineHeightPx,
    fontFamily: bodyFontFamily(theme),
  };
}

/**
 * Render a {@link ButtonTokens} as the inline `style` custom-property string the component binds.
 * Every entry is a `--eden-button-*` var whose VALUE is a derived token — the markup references
 * `var(--eden-button-bg)` etc. and carries no literal. This is the seam that keeps the *.svelte
 * file free of hand-set colors/sizes (the no-hand-set-hex provenance lint passes by construction).
 */
export function buttonStyleVars(tokens: ButtonTokens): string {
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-fg`, tokens.foreground],
    [`${VAR_PREFIX}-bg`, tokens.background],
    [`${VAR_PREFIX}-border`, tokens.border],
    [`${VAR_PREFIX}-hit-target`, `${String(tokens.hitTargetPx)}px`],
    [`${VAR_PREFIX}-height`, `${String(tokens.heightPx)}px`],
    [`${VAR_PREFIX}-padding-inline`, `${String(tokens.paddingInlinePx)}px`],
    [`${VAR_PREFIX}-padding-block`, `${String(tokens.paddingBlockPx)}px`],
    [`${VAR_PREFIX}-gap`, `${String(tokens.gapPx)}px`],
    [`${VAR_PREFIX}-font-size`, `${String(tokens.fontSizePx)}px`],
    [`${VAR_PREFIX}-line-height`, `${String(tokens.lineHeightPx)}px`],
    [`${VAR_PREFIX}-font-family`, tokens.fontFamily],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}

/**
 * The default theme the Button derives from when a host does not inject one: the C21 reference
 * brand seed run through `generateTheme`. A host overrides by passing its own theme (the wiring is
 * the `theme` prop on the component); the SEED is the only literal crossing and it lives in
 * `@eden/theme` (cited here, never re-spelled — one concept, one home).
 */
export function defaultButtonTheme(options?: GenerateOptions): Theme {
  return generateTheme(C21_SEED, options);
}

/** Re-export the seed type so a host can type its own seed without reaching past this barrel. */
export type { ThemeSeed };
