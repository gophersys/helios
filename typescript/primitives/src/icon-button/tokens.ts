/**
 * `@eden/primitives` — IconButton token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. An IconButton is a SQUARE, icon-only button: it reuses the Button's
 * variant→role selection (one concept, one home — it CITES {@link deriveButtonTokens}, never
 * re-derives the fg/bg pair) and adds the square-geometry decisions, all READ OUT of a generated
 * {@link Theme}. The icon glyph is sized from the theme's `controlGeometry.iconSizePx` (a scale
 * value), and the square edge is the SAME hit-target floor the Button guarantees — so a square
 * icon-only control never falls below the 44px AAA tap area. This module decides NOTHING by hand:
 * every color/size/space is a property of the theme, asserted in `icon-button.design.test.ts`.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import { deriveButtonTokens, type ButtonVariant } from '../button/tokens.js';

/** The CSS-variable namespace every IconButton custom property carries (one prefix). */
const VAR_PREFIX = '--eden-icon-button';

/**
 * The resolved token set an IconButton instance renders from. The color trio is the SAME role
 * selection the Button makes (cited), and the geometry is the square-control geometry: the visual
 * edge is the component height, the accessible edge is the decoupled hit target, and the glyph is
 * the theme's icon size. The raw OKLCH pair rides alongside so the design-correctness gate can
 * recompute contrast from the SAME numbers the CSS carries.
 */
export interface IconButtonTokens {
  /** The foreground (icon) color as a CSS `oklch(...)` string. */
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
  /** The visual square edge, px (theme.controlGeometry.componentHeightPx — on the 4px grid). */
  readonly sizePx: number;
  /** The icon glyph size, px (theme.controlGeometry.iconSizePx — a scale value, not eyeballed). */
  readonly iconSizePx: number;
}

/**
 * Derive the full {@link IconButtonTokens} for a variant from a generated theme. PURE: the theme is
 * the single input. The color trio is delegated to {@link deriveButtonTokens} (the Button is the
 * ONE home of the variant→role mapping — an IconButton is a Button shaped square), and the
 * square geometry is read from the same `controlGeometry`.
 */
export function deriveIconButtonTokens(variant: ButtonVariant, theme: Theme): IconButtonTokens {
  // Cite the Button's role selection — one concept, one home (10 §9): do NOT re-spell the
  // variant→{fg,bg,border} mapping here. The IconButton differs only in SHAPE, not in color logic.
  const base = deriveButtonTokens(variant, theme);
  const g = theme.controlGeometry;
  return {
    foreground: base.foreground,
    background: base.background,
    border: base.border,
    foregroundOklch: base.foregroundOklch,
    backgroundOklch: base.backgroundOklch,
    hitTargetPx: g.hitTargetPx,
    sizePx: g.componentHeightPx,
    iconSizePx: g.iconSizePx,
  };
}

/**
 * Render an {@link IconButtonTokens} as the inline `style` custom-property string the component
 * binds. Every entry is a `--eden-icon-button-*` var whose VALUE is a derived token — the markup
 * references `var(--eden-icon-button-*)` only and carries no literal (the provenance lint passes by
 * construction).
 */
export function iconButtonStyleVars(tokens: IconButtonTokens): string {
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-fg`, oklchToCss(tokens.foregroundOklch)],
    [`${VAR_PREFIX}-bg`, oklchToCss(tokens.backgroundOklch)],
    [`${VAR_PREFIX}-border`, tokens.border],
    [`${VAR_PREFIX}-hit-target`, `${String(tokens.hitTargetPx)}px`],
    [`${VAR_PREFIX}-size`, `${String(tokens.sizePx)}px`],
    [`${VAR_PREFIX}-icon-size`, `${String(tokens.iconSizePx)}px`],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}
