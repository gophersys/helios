/**
 * `@eden/primitives` — Field token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. A Field is the label + control + error-message group. It decides NOTHING
 * by hand: the label text color (`onSurface`), the error-message text color (`error`), the label
 * font, and the vertical rhythm between the three parts are all READ OUT of a generated
 * {@link Theme}. Both text colors are recomputed against @eden/theme's contrast gate in
 * `field.design.test.ts` (the label over the surface, the error message over the surface), so a
 * legible label and a legible error message are a passing gate, not a judgement call.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';

/** The CSS-variable namespace every Field custom property carries (one prefix, derived names). */
const VAR_PREFIX = '--eden-field';

/**
 * The resolved token set a Field instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH text colors ride alongside so the design-correctness gate
 * can recompute the contrast ratio from the SAME numbers the CSS carries.
 */
export interface FieldTokens {
  /** The label text color as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly label: string;
  /** The error-message text color as a CSS `oklch(...)` string — the `error` role. */
  readonly error: string;
  /** The surface the Field is read against as a CSS `oklch(...)` string — the `surface` role. */
  readonly surface: string;
  /** The raw OKLCH of the label — the contrast gate recomputes the ratio against the surface. */
  readonly labelOklch: OkLch;
  /** The raw OKLCH of the error message — the contrast gate recomputes the ratio against surface. */
  readonly errorOklch: OkLch;
  /** The raw OKLCH of the surface — the background both texts are read against. */
  readonly surfaceOklch: OkLch;
  /** The gap between the label, the control, and the error message, px (theme.spacing — a ramp step). */
  readonly gapPx: number;
  /** The label font size, px — the theme's `label` typography role (or `body` fallback). */
  readonly labelFontSizePx: number;
  /** The label line height, px (derived from the label typography role's unitless line height). */
  readonly labelLineHeightPx: number;
  /** The label font family — the theme's `label` (or `body`) typography role family. */
  readonly labelFontFamily: string;
}

/** Find a typography role by name, falling back to `body`, then the first role. */
function roleByName(theme: Theme, name: string): Theme['typography'][number] | undefined {
  return (
    theme.typography.find((r) => r.name === name) ??
    theme.typography.find((r) => r.name === 'body') ??
    theme.typography[0]
  );
}

/**
 * Derive the full {@link FieldTokens} from a generated theme. PURE: the theme is the single input.
 * `deriveFieldTokens` is the function the design-correctness gate audits and the Field renders from.
 * The label uses the theme's `label` typography role when present (a smaller, denser role than body),
 * falling back to `body` — a SCALE selection, never a hand-set size.
 */
export function deriveFieldTokens(theme: Theme): FieldTokens {
  const roles = theme.roles;
  const labelRole = roleByName(theme, 'label');
  const labelFontSizePx = labelRole ? labelRole.fontSizePx : theme.controlGeometry.fontSizePx;
  // The line height is the typography role's unitless ratio × its font size, rounded to a whole px
  // (a derived value, not eyeballed). The fallback uses the control line height.
  const labelLineHeightPx = labelRole
    ? Math.round(labelRole.fontSizePx * labelRole.lineHeight)
    : theme.controlGeometry.lineHeightPx;
  return {
    label: oklchToCss(roles.onSurface.value),
    error: oklchToCss(roles.error.value),
    surface: oklchToCss(roles.surface.value),
    labelOklch: roles.onSurface.value,
    errorOklch: roles.error.value,
    surfaceOklch: roles.surface.value,
    // The vertical rhythm is the control inset (a single ramp step) — the same scale the field uses,
    // so the label↔control↔error spacing reads as one rhythm. A SCALE value, never hand-set.
    gapPx: theme.controlGeometry.insetPx,
    labelFontSizePx,
    labelLineHeightPx,
    labelFontFamily: labelRole ? labelRole.fontFamily : 'inherit',
  };
}

/**
 * Render a {@link FieldTokens} as the inline `style` custom-property string the component binds.
 * Every entry is an `--eden-field-*` var whose VALUE is a derived token — the markup references
 * `var(--eden-field-*)` only and carries no literal (the provenance lint passes by construction).
 */
export function fieldStyleVars(tokens: FieldTokens): string {
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-label`, tokens.label],
    [`${VAR_PREFIX}-error`, tokens.error],
    [`${VAR_PREFIX}-surface`, tokens.surface],
    [`${VAR_PREFIX}-gap`, `${String(tokens.gapPx)}px`],
    [`${VAR_PREFIX}-label-font-size`, `${String(tokens.labelFontSizePx)}px`],
    [`${VAR_PREFIX}-label-line-height`, `${String(tokens.labelLineHeightPx)}px`],
    [`${VAR_PREFIX}-label-font-family`, tokens.labelFontFamily],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}
