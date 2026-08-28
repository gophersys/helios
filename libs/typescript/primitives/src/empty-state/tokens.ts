/**
 * `@eden/primitives` — EmptyState token derivation (ADR-0024 §3, doc 17 §4 molecules).
 *
 * MATH IS SOURCE OF TRUTH. An EmptyState is a PRODUCT SURFACE, never a bare void (doc 17 §1.2): a
 * serif-display HEADLINE, a sans BODY line, a primary ACTION, and an optional content SLOT (recents/
 * templates). It decides NOTHING by hand: the headline is the `display-small` typography role — the
 * SERIF DISPLAY VOICE doc 17 §4 mandates for an empty-state headline (an identity moment, P-D4), the
 * body is the `body` role (the sans interface voice), the headline colour is `onSurface` and the body
 * colour `outline` (a quieter secondary line — both AA-legible over the surface), and the vertical
 * rhythm + the max reading width come from the spacing ramp (chat-surface `space`) / the theme
 * `breakpoints`. Every value is derived; this module CITES the shared homes and re-spells no role
 * selection, ramp lookup, or px.
 *
 * The serif voice is proven honest by the design lane: the headline's font family MUST equal the
 * theme's `display-*` role family (the seed's DISPLAY font), not the text font — so "serif display
 * headline" is a checked property, not a comment.
 */

import { oklchToCss, type Theme, type OkLch, type TypographyRole } from '@eden/theme';
import { proportion, space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** The CSS-variable namespace every EmptyState custom property carries. */
const VAR_PREFIX = '--eden-empty-state';

/**
 * The resolved token set an EmptyState instance renders from. Every field is a CSS value DERIVED from
 * a generated {@link Theme}. The raw OKLCH headline/body/surface triple rides alongside so the
 * design-correctness gate recomputes both contrast ratios from the SAME numbers the CSS carries.
 */
export interface EmptyStateTokens {
  /** The headline text colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly headline: string;
  /** The body text colour as a CSS `oklch(...)` string — the `outline` role (a quieter secondary line). */
  readonly body: string;
  /** The surface the empty state is read against as a CSS `oklch(...)` string — the `surface` role. */
  readonly surface: string;
  /** The raw OKLCH of the headline — the contrast gate recomputes the ratio against the surface. */
  readonly headlineOklch: OkLch;
  /** The raw OKLCH of the body — the contrast gate recomputes the ratio against the surface. */
  readonly bodyOklch: OkLch;
  /** The raw OKLCH of the surface — the background both texts are read against. */
  readonly surfaceOklch: OkLch;
  /** The headline font size, px — the `display-small` typography role (the serif display voice). */
  readonly headlineFontSizePx: number;
  /** The headline line height, px — the `display-small` role's generated line height. */
  readonly headlineLineHeightPx: number;
  /** The headline font family — the `display-small` role family (the seed DISPLAY/serif font). */
  readonly headlineFontFamily: string;
  /** The body font size, px — the `body` typography role (the sans interface voice). */
  readonly bodyFontSizePx: number;
  /** The body line height, px — the `body` role's generated line height. */
  readonly bodyLineHeightPx: number;
  /** The body font family — the `body` role family (the seed TEXT/sans font). */
  readonly bodyFontFamily: string;
  /** The vertical rhythm between headline / body / action / slot, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The interior padding around the empty-state surface, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The max reading width, px — the theme's `medium` breakpoint (a real layout measure, not eyeballed). */
  readonly maxWidthPx: number;
}

/** Find the theme's `medium` breakpoint min-width as the empty-state reading measure (cites the theme). */
function readingMeasurePx(theme: Theme): number {
  const bp = theme.breakpoints.find((b) => b.name === 'medium') ?? theme.breakpoints[0];
  // Every generated theme carries the Material window classes (research Table B2-B); the fallback
  // keeps the function total. `medium` (600px) is the focus-content measure — wide enough to read,
  // narrow enough not to sprawl (the anti-void: doc 17 §1.2).
  return bp ? bp.minWidthPx : 600;
}

/** The empty-state headline typography role — `display-small` (the serif display voice, doc 17 §4). */
function headlineRole(theme: Theme): TypographyRole | undefined {
  return (
    theme.typography.find((r) => r.name === 'display-small') ??
    theme.typography.find((r) => r.name === 'headline') ??
    theme.typography[0]
  );
}

/**
 * Derive the full {@link EmptyStateTokens} from a generated theme. PURE: the theme is the single
 * input. The headline is the `display-small` SERIF role, the body the `body` SANS role — nothing is
 * re-spelled here.
 */
export function deriveEmptyStateTokens(theme: Theme): EmptyStateTokens {
  const roles = theme.roles;
  const head = headlineRole(theme);
  const body = proportion(theme, 'body');
  const headlineFontSizePx = head ? head.fontSizePx : theme.controlGeometry.fontSizePx;
  const headlineLineHeightPx = head
    ? Math.round(head.fontSizePx * head.lineHeight)
    : theme.controlGeometry.lineHeightPx;
  return {
    headline: oklchToCss(roles.onSurface.value),
    body: oklchToCss(roles.outline.value),
    surface: oklchToCss(roles.surface.value),
    headlineOklch: roles.onSurface.value,
    bodyOklch: roles.outline.value,
    surfaceOklch: roles.surface.value,
    headlineFontSizePx,
    headlineLineHeightPx,
    headlineFontFamily: head ? head.fontFamily : 'inherit',
    bodyFontSizePx: body.fontSizePx,
    bodyLineHeightPx: body.lineHeightPx,
    bodyFontFamily: body.fontFamily,
    // The rhythm is `space-4` (16px); the interior padding `space-8` (32px) — generous for a focus
    // moment (doc 17 §5: generosity only for focus moments), both ramp steps.
    gapPx: space(theme, 4),
    paddingPx: space(theme, 7),
    maxWidthPx: readingMeasurePx(theme),
  };
}

/**
 * Render an {@link EmptyStateTokens} as the inline `style` custom-property string the component binds.
 * Cites the shared `styleVars` emitter — the markup references `var(--eden-empty-state-*)` only.
 */
export function emptyStateStyleVars(tokens: EmptyStateTokens): string {
  const entries: readonly StyleEntry[] = [
    ['headline', tokens.headline],
    ['body', tokens.body],
    ['surface', tokens.surface],
    ['headline-font-size', tokens.headlineFontSizePx],
    ['headline-line-height', tokens.headlineLineHeightPx],
    ['headline-font-family', tokens.headlineFontFamily],
    ['body-font-size', tokens.bodyFontSizePx],
    ['body-line-height', tokens.bodyLineHeightPx],
    ['body-font-family', tokens.bodyFontFamily],
    ['gap', tokens.gapPx],
    ['padding', tokens.paddingPx],
    ['max-width', tokens.maxWidthPx],
  ];
  return styleVars(VAR_PREFIX, entries);
}
