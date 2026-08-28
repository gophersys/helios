/**
 * `@eden/primitives` — Spinner token derivation (ADR-0024 §3, doc 17 §4 atoms).
 *
 * MATH IS SOURCE OF TRUTH. A Spinner is the loading atom. It decides NOTHING by hand: the arc colour
 * is the theme's `primary` role (or, when carrying a status, a status role via surface-tokens), the
 * track is the `outline` role, the DIAMETER is the theme's `controlGeometry.iconSizePx` (an on-grid
 * icon dimension) so the spinner sits exactly where an icon would, the stroke width is a spacing-ramp
 * step (chat-surface `space`), and — critically — the ROTATION DURATION + EASING are the theme's
 * MOTION tokens (`motion.durations` + `motion.easing.linear`), never a hand-typed `1s`. Every value
 * is derived; this module CITES the shared homes and re-spells no role selection, ramp lookup, px, or
 * duration.
 *
 * A spinner rotates at CONSTANT angular velocity → the `linear` easing (research Table B5-B), and a
 * ~900ms period (the `extra-long.3` duration-ladder rung) reads as a calm, purposeful loop rather
 * than an anxious blur. `prefers-reduced-motion` is honored in the component CSS (the animation is
 * suppressed and the arc holds static), so the motion is opt-out by construction (doc 17 §5).
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import { statusRoleOklch, type Status } from '../surface-tokens/tokens.js';
import { space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** A Spinner variant — `accent` (the brand primary) or a status role (the Clusters vocabulary). */
export type SpinnerVariant = 'accent' | Status;

/** The CSS-variable namespace every Spinner custom property carries. */
const VAR_PREFIX = '--eden-spinner';

/** The rotation-period duration-ladder rung — a calm, constant loop (~900ms). Cited, never typed. */
const ROTATION_DURATION_TOKEN = 'extra-long.3';

/** The constant-velocity easing a rotating spinner uses (research Table B5-B `linear`). Cited. */
const ROTATION_EASING_TOKEN = 'linear';

/**
 * The resolved token set a Spinner instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH arc/track colours ride alongside so the design-correctness
 * gate recomputes the arc-over-surface contrast from the SAME numbers the CSS carries.
 */
export interface SpinnerTokens {
  /** The active arc colour as a CSS `oklch(...)` string — the `primary` or a status role. */
  readonly arc: string;
  /** The track (idle ring) colour as a CSS `oklch(...)` string — the `outline` role. */
  readonly track: string;
  /** The raw OKLCH of the arc — the contrast gate recomputes the ratio against the surface. */
  readonly arcOklch: OkLch;
  /** The raw OKLCH of the surface the spinner is read against — the contrast gate's background. */
  readonly surfaceOklch: OkLch;
  /** The diameter, px — the theme's `controlGeometry.iconSizePx` (an on-grid icon dimension). */
  readonly sizePx: number;
  /** The ring stroke width, px — a spacing-ramp step (chat-surface space). */
  readonly strokePx: number;
  /** The rotation period, ms — a `motion.durations` ladder rung (never a hand-typed duration). */
  readonly durationMs: number;
  /** The rotation easing — a `motion.easing` curve as a CSS `cubic-bezier(...)` string. */
  readonly easing: string;
}

/** Resolve a Spinner variant to its arc-colour OKLCH (accent → primary; else the status role). */
function arcRoleOklch(variant: SpinnerVariant, theme: Theme): OkLch {
  return variant === 'accent' ? theme.roles.primary.value : statusRoleOklch(variant, theme);
}

/** Render a `motion.easing` cubic-bezier tuple as a CSS `cubic-bezier(...)` string. */
function easingCss(theme: Theme, token: string): string {
  const bezier = theme.motion.easing[token] ?? theme.motion.easing['linear'];
  // Every generated theme carries the `linear` easing (research Table B5-B); the fallback keeps the
  // function total. `[...]` copies the readonly tuple so join is on a plain array.
  const b = bezier ?? [0, 0, 1, 1];
  return `cubic-bezier(${[...b].join(', ')})`;
}

/**
 * Derive the full {@link SpinnerTokens} for a variant from a generated theme. PURE: the theme is the
 * single input. The diameter is the theme's icon dimension; the duration + easing are the theme's
 * motion tokens — nothing is re-spelled here.
 */
export function deriveSpinnerTokens(variant: SpinnerVariant, theme: Theme): SpinnerTokens {
  const arc = arcRoleOklch(variant, theme);
  return {
    arc: oklchToCss(arc),
    track: oklchToCss(theme.roles.outline.value),
    arcOklch: arc,
    surfaceOklch: theme.roles.surface.value,
    sizePx: theme.controlGeometry.iconSizePx,
    // The stroke is `space-0.5` (2px) — the thinnest ramp step, a crisp ring at icon scale.
    strokePx: space(theme, 0),
    durationMs: theme.motion.durations[ROTATION_DURATION_TOKEN],
    easing: easingCss(theme, ROTATION_EASING_TOKEN),
  };
}

/**
 * Render a {@link SpinnerTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter. A ms duration and the easing string are string-valued (they
 * carry their own unit / are already a CSS function), so they pass through the emitter verbatim.
 */
export function spinnerStyleVars(tokens: SpinnerTokens): string {
  const entries: readonly StyleEntry[] = [
    ['arc', tokens.arc],
    ['track', tokens.track],
    ['size', tokens.sizePx],
    ['stroke', tokens.strokePx],
    ['duration', `${String(tokens.durationMs)}ms`],
    ['easing', tokens.easing],
  ];
  return styleVars(VAR_PREFIX, entries);
}
