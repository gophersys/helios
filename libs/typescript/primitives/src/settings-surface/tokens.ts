/**
 * `@eden/primitives` — SettingsSurface token derivation (ADR-0024 §3, doc 17 §4 organisms / §7 Settings).
 *
 * MATH IS SOURCE OF TRUTH, and ONE CONCEPT ONE HOME (10 §9). The SettingsSurface is the sheet-hosted
 * Settings organism doc 17 §4 names and §7 rules: a left SECTION RAIL (mono/eyebrow section labels with
 * an active state) beside a CONTENT AREA rendered per active section. It is a SELECTION of the shared
 * overlay surface (the sheet layer — the same portaled Dialog behavior the app already trusts), plus a
 * small set of rail-specific role picks. It decides NOTHING by hand:
 *
 *   - the sheet SURFACE / on-surface / outline / scrim / elevation / z-index / radius are the shared
 *     {@link deriveOverlayTokens} at the `modal` layer (the sheet is a focus-modal — one home);
 *   - a section label is the `label` typography role over the seed's MONO family (the mono data voice,
 *     P-D4 — the same generic-`monospace` citation Chip / Kbd / WizardShell keep), rendered in the
 *     `outline` role when INACTIVE and the `primary` accent when ACTIVE (both AA-legible over the sheet
 *     surface / the active rail tint, asserted in the design lane);
 *   - the active rail item carries a soft `primary` TINT wash (a translucent VIEW of the accent, the
 *     Clusters chip idiom) so the selection reads without colour being the only channel (the label also
 *     changes weight + carries `aria-current`);
 *   - a section TITLE (the content-area heading) is the `title` typography role in `onSurface` (the sans
 *     interface voice); the rhythm + rail width come from the spacing ramp and a generated breakpoint.
 *
 * Every value is derived; this module CITES the shared homes (overlay `deriveOverlayTokens`, surface-tokens
 * `radiusPx`/`statusTint`, chat-surface `proportion`/`space`/`styleVars`) and re-spells no role selection,
 * ramp lookup, radius, shadow, or px. The design-correctness gate recomputes the inactive-label, the
 * active-label, and the section-title contrast from the SAME OKLCH the CSS carries (the raw triples ride
 * alongside), asserts the label voice is the MONO generic, and asserts the rail width is a generated
 * breakpoint — so "mono section labels", "AA active/inactive", and "on the scale" are checked properties.
 */

import { oklchToCss, type Theme, type OkLch } from '@eden/theme';
import { deriveOverlayTokens } from '../overlay/tokens.js';
import { radiusPx, statusTint } from '../surface-tokens/tokens.js';
import { proportion, space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** The CSS-variable namespace every SettingsSurface custom property carries. */
const VAR_PREFIX = '--eden-settings-surface';

/**
 * The section-label MONO family. As with Chip / Kbd / WizardShell (one home), the seed's `fonts.code`
 * is not re-emitted onto any generated typography role, so the honest citation for the mono data voice
 * is the CSS GENERIC `monospace` keyword — a generic, never a hand-set font NAME. Only the FAMILY is the
 * generic; the SIZE is still a generated scale value (the `label` role). When @eden/theme later emits a
 * code-typography role, this one line swaps to cite it.
 */
const MONO_FAMILY = 'monospace';

/** The active-rail tint alpha — a soft wash of the accent behind the active section label. A fraction
 *  (a translucent VIEW of the `primary` role via {@link statusTint}), never a colour literal. */
const ACTIVE_TINT_ALPHA = 0.14;

/**
 * The resolved token set a SettingsSurface instance renders from. Every field is a CSS value DERIVED
 * from a generated {@link Theme}. The raw OKLCH label/active/title/surface quad rides alongside so the
 * design gate recomputes each contrast ratio from the SAME numbers the CSS carries (the proof audits the
 * emitted value, never a copy).
 */
export interface SettingsSurfaceTokens {
  /** The sheet surface fill as a CSS `oklch(...)` string — the overlay `surface` role. */
  readonly surface: string;
  /** The on-surface (body/content) foreground as a CSS `oklch(...)` string — the overlay `onSurface` role. */
  readonly onSurface: string;
  /** The hairline separator colour as a CSS `oklch(...)` string — the overlay `outline` role. */
  readonly outline: string;
  /** The scrim (modal backdrop) colour as a CSS `oklch(...)` string — the overlay scrim. */
  readonly scrim: string;
  /** The INACTIVE section-label colour as a CSS `oklch(...)` string — the `outline` role (a quiet rail item). */
  readonly labelInactive: string;
  /** The ACTIVE section-label colour as a CSS `oklch(...)` string — the `primary` accent role. */
  readonly labelActive: string;
  /** The active rail item's TINT wash as a CSS `oklch(L C H / a)` string — a translucent view of `primary`. */
  readonly activeTint: string;
  /** The section-TITLE (content heading) colour as a CSS `oklch(...)` string — the `onSurface` role. */
  readonly title: string;
  /** The raw OKLCH of the surface — the background the labels + the title are read against. */
  readonly surfaceOklch: OkLch;
  /** The raw OKLCH of the inactive label — the contrast gate recomputes the ratio over the surface. */
  readonly labelInactiveOklch: OkLch;
  /** The raw OKLCH of the active label — the contrast gate recomputes the ratio over the surface. */
  readonly labelActiveOklch: OkLch;
  /** The raw OKLCH of the section title — the contrast gate recomputes the ratio over the surface. */
  readonly titleOklch: OkLch;
  /** The section-label font size, px — the `label` typography role (the mono data voice). */
  readonly labelFontSizePx: number;
  /** The section-label line height, px — the `label` role's generated line height. */
  readonly labelLineHeightPx: number;
  /** The section-label font family — the CSS generic `monospace` (the data voice, P-D4). */
  readonly labelFontFamily: string;
  /** The section-title font size, px — the `title` typography role (the sans interface voice). */
  readonly titleFontSizePx: number;
  /** The section-title line height, px — the `title` role's generated line height. */
  readonly titleLineHeightPx: number;
  /** The section-title font family — the `title` role family (the seed TEXT/sans font). */
  readonly titleFontFamily: string;
  /** The sheet corner radius, px — the `sheet` radius (the largest ramp radius, for a side sheet). */
  readonly radiusPx: number;
  /** The rail-item / content control radius, px — the `control` radius (the tightest, for a rail row). */
  readonly itemRadiusPx: number;
  /** The section-rail column width, px — a fraction of the `medium` breakpoint: a real layout measure. */
  readonly railWidthPx: number;
  /** The interior padding around the sheet, px — a spacing-ramp step. */
  readonly paddingPx: number;
  /** The vertical rhythm between rail items / content blocks, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The rail-item inline padding, px — a spacing-ramp step. */
  readonly itemPaddingPx: number;
  /** The decoupled AAA hit target, px — the overlay `hitTarget` (≥44, the rail rows never shrink below). */
  readonly hitTargetPx: number;
  /** The composed elevation `box-shadow` — the overlay sheet lift. */
  readonly elevationShadow: string;
  /** The z-index ordinal — the overlay modal rung (the sheet stacks at the modal layer). */
  readonly zIndex: number;
}

/** The rail column width — a fraction of the `medium` window class (600px → ≈162px), a real layout
 *  measure drawn from a generated breakpoint, never an eyeballed 160. (`compact` is the base window at
 *  0px, so `medium` is the smallest NON-ZERO measure — the same one EmptyState reads its cap from.)
 *  Falls back to the first non-zero breakpoint then 600 so the pick is total and always positive. */
function railMeasurePx(theme: Theme): number {
  const bp =
    theme.breakpoints.find((b) => b.name === 'medium') ??
    theme.breakpoints.find((b) => b.minWidthPx > 0) ??
    theme.breakpoints[0];
  const base = bp && bp.minWidthPx > 0 ? bp.minWidthPx : 600;
  // A rail is roughly a quarter-and-a-bit of a medium window — wide enough for a mono section label,
  // narrow enough to leave the content area the room. The multiplier is the ONE proportion decision.
  return Math.round(base * 0.27);
}

/**
 * Derive the full {@link SettingsSurfaceTokens} from a generated theme. PURE: the theme is the single
 * input (the New(configuration) spine, rule 10). The sheet surface/scrim/elevation/z/radius are the
 * shared overlay `modal` tokens; the rail labels are the mono `label` voice (outline inactive / primary
 * active); the active tint is a translucent view of `primary`; the section title is the sans `title`
 * role — nothing is re-spelled here. `deriveSettingsSurfaceTokens` is the function the design gate audits
 * and the component renders from.
 */
export function deriveSettingsSurfaceTokens(theme: Theme): SettingsSurfaceTokens {
  const roles = theme.roles;
  const overlay = deriveOverlayTokens('modal', theme);
  const label = proportion(theme, 'label');
  const title = proportion(theme, 'title');
  return {
    surface: overlay.surface,
    onSurface: overlay.onSurface,
    outline: overlay.outline,
    scrim: overlay.scrim,
    labelInactive: oklchToCss(roles.outline.value),
    labelActive: oklchToCss(roles.primary.value),
    activeTint: statusTint('accent', theme, ACTIVE_TINT_ALPHA),
    title: oklchToCss(roles.onSurface.value),
    surfaceOklch: overlay.surfaceOklch,
    labelInactiveOklch: roles.outline.value,
    labelActiveOklch: roles.primary.value,
    titleOklch: roles.onSurface.value,
    labelFontSizePx: label.fontSizePx,
    labelLineHeightPx: label.lineHeightPx,
    labelFontFamily: MONO_FAMILY,
    titleFontSizePx: title.fontSizePx,
    titleLineHeightPx: title.lineHeightPx,
    titleFontFamily: title.fontFamily,
    // The sheet is the LARGEST radius (`sheet`), the rail rows the TIGHTEST (`control`) — the same
    // monotone radius set doc 17 §3 rules, drawn from the ONE ramp.
    radiusPx: radiusPx(theme, 'sheet'),
    itemRadiusPx: radiusPx(theme, 'control'),
    railWidthPx: railMeasurePx(theme),
    // The interior padding is `space-6` (24px) and the rhythm `space-3` (12px) — both ramp steps; the
    // rail-item inline padding `space-3` too. Generous for a focus sheet (§5) without sprawling.
    paddingPx: space(theme, 6),
    gapPx: space(theme, 3),
    itemPaddingPx: space(theme, 3),
    hitTargetPx: overlay.hitTargetPx,
    elevationShadow: overlay.elevationShadow,
    zIndex: overlay.zIndex,
  };
}

/**
 * Render a {@link SettingsSurfaceTokens} as the inline `style` custom-property string the portaled sheet
 * binds. Cites the shared `styleVars` emitter — the markup references `var(--eden-settings-surface-*)`
 * only. Colour values pass through verbatim (already `oklch(...)`); numerics are px-suffixed; the shadow
 * + z-index are pre-formatted strings (a composed shadow / a bare ordinal) so they bypass the px suffix.
 */
export function settingsSurfaceStyleVars(tokens: SettingsSurfaceTokens): string {
  const entries: readonly StyleEntry[] = [
    ['surface', tokens.surface],
    ['on-surface', tokens.onSurface],
    ['outline', tokens.outline],
    ['scrim', tokens.scrim],
    ['label-inactive', tokens.labelInactive],
    ['label-active', tokens.labelActive],
    ['active-tint', tokens.activeTint],
    ['title', tokens.title],
    ['label-font-size', tokens.labelFontSizePx],
    ['label-line-height', tokens.labelLineHeightPx],
    ['label-font-family', tokens.labelFontFamily],
    ['title-font-size', tokens.titleFontSizePx],
    ['title-line-height', tokens.titleLineHeightPx],
    ['title-font-family', tokens.titleFontFamily],
    ['radius', tokens.radiusPx],
    ['item-radius', tokens.itemRadiusPx],
    ['rail-width', tokens.railWidthPx],
    ['padding', tokens.paddingPx],
    ['gap', tokens.gapPx],
    ['item-padding', tokens.itemPaddingPx],
    ['hit-target', tokens.hitTargetPx],
    ['shadow', tokens.elevationShadow],
    ['z', String(tokens.zIndex)],
  ];
  return styleVars(VAR_PREFIX, entries);
}

/**
 * One settings SECTION's rail metadata — the mono label the rail renders + the stable id the surface
 * selects a section by (the content is a per-section snippet the consumer supplies). The declaration
 * lives here (the token home) so the barrel re-exports it from one place — the same shape Tabs `Tab` /
 * WizardShell `WizardStep` keep.
 */
export interface SettingsSection {
  /** The stable section id (the surface's `active` prop selects a section by this). */
  readonly id: string;
  /** The mono, eyebrow section label the rail renders (e.g. "Profile", "Appearance"). */
  readonly label: string;
}
