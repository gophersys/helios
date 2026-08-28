/**
 * `@eden/primitives` — WizardShell token derivation (ADR-0024 §3, doc 17 §6 the wizard pattern).
 *
 * MATH IS SOURCE OF TRUTH, and ONE CONCEPT ONE HOME (10 §9). The WizardShell is the FULL-SCREEN focus
 * organism doc 17 §6 rules: one question per screen, the SERIF DISPLAY question at the LARGEST step, a
 * mono `1 / 3` counter, a THIN top progress bar, Enter advances, Esc offers exit. It decides NOTHING
 * by hand: the TITLE is the `display-large` typography role (the biggest generated display step — doc
 * 17 §6's "serif display at the largest step", the identity-moment voice P-D4), the LEAD is `body-large`
 * (the ruling's "helper ≤ 1 sentence", the sans interface voice), the EYEBROW + COUNTER are the mono
 * data voice (`caption` role over the seed's mono/code family — the `1 / 3` counter is a Chip/Kbd-class
 * mono datum), the reading MEASURE for the content region is a generated breakpoint (`expanded`, 840px
 * — wide enough for a question + input, narrow enough not to sprawl; a scale value, never eyeballed),
 * the progress bar's height + track colours are ramp/role selections, and its transition rides the
 * theme's MOTION slice (`motion.durations['medium.2']` + the `standard` easing) so the fill animates on
 * the same math the theme emits — reduced-motion honored in the template. Every value is derived; this
 * module CITES the shared homes (chat-surface `proportion`/`space`/`styleVars`, surface-tokens
 * `radiusPx`) and re-spells no role selection, ramp lookup, radius, or px.
 *
 * The design-correctness gate recomputes both the title-over-surface and the lead-over-surface contrast
 * from the SAME OKLCH the CSS carries (the raw triple rides alongside), asserts the title size EQUALS
 * the generated `display-large` step, asserts the measure IS a generated breakpoint, and asserts the
 * progress-bar FRACTION math (index / (count − 1)) is exact — so "largest display step", "on the scale",
 * and "the fill is the fraction" are checked properties, not comments.
 */

import { oklchToCss, type Theme, type OkLch, type TypographyRole } from '@eden/theme';
import { radiusPx } from '../surface-tokens/tokens.js';
import { proportion, space, styleVars, type StyleEntry } from '../chat-surface/tokens.js';

/** The CSS-variable namespace every WizardShell custom property carries. */
const VAR_PREFIX = '--eden-wizard-shell';

/**
 * One step's metadata — the copy the shell renders for the active screen (doc 17 §6 copy budgets:
 * the title is the ≤ 6-word question; the lead is the ≤ 1-sentence helper). The declaration lives here
 * (the token home) so the barrel re-exports it from one place — the same shape Tabs `Tab` / StatRow
 * `Stat` keep. The shell picks the active step by {@link WizardStep.id} and reads its copy verbatim.
 */
export interface WizardStep {
  /** The stable step id (the shell's `active` prop selects a step by this). */
  readonly id: string;
  /** The mono, uppercase, tracked eyebrow (optional — a small orienting overline). */
  readonly eyebrow?: string;
  /** The serif-display question — the identity moment (budget: ≤ 6 words, doc 17 §6). */
  readonly title: string;
  /** The one-sentence helper lead (optional — budget: ≤ 1 sentence, doc 17 §6). */
  readonly lead?: string;
}

/**
 * The eyebrow + counter MONO family. The seed's `fonts.code` (JetBrains Mono for C21) is NOT
 * re-emitted onto any generated typography role (every role renders in the `display`/serif or
 * `text`/sans face — see @eden/theme generate.ts / css.ts), so the honest citation for the wizard's
 * mono data voice is the CSS GENERIC `monospace` keyword — the platform's always-available mono, a
 * generic keyword never a hand-set font NAME, EXACTLY as Chip / Kbd / StatRow cite it (one home). The
 * mono SIZE is still a generated scale value (the `caption` role); only the FAMILY is the generic.
 * When @eden/theme later emits a code-typography role, this one line swaps to cite it.
 */
const MONO_FAMILY = 'monospace';

/**
 * The resolved token set a WizardShell instance renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme}. The raw OKLCH title/lead/surface triple rides alongside so the design gate
 * recomputes both contrast ratios from the SAME numbers the CSS carries (the proof audits the emitted
 * value, never a copy).
 */
export interface WizardShellTokens {
  /** The full-viewport surface fill as a CSS `oklch(...)` string — the `surface` role. */
  readonly surface: string;
  /** The title text colour as a CSS `oklch(...)` string — the `onSurface` role (the identity voice). */
  readonly title: string;
  /** The lead text colour as a CSS `oklch(...)` string — the `outline` role (a quieter helper line). */
  readonly lead: string;
  /** The eyebrow + counter mono colour as a CSS `oklch(...)` string — the `primary` accent role. */
  readonly accent: string;
  /** The progress-bar TRACK colour as a CSS `oklch(...)` string — the `outline` role (a quiet rail). */
  readonly track: string;
  /** The progress-bar FILL colour as a CSS `oklch(...)` string — the `primary` accent role. */
  readonly fill: string;
  /** The raw OKLCH of the title — the contrast gate recomputes the ratio against the surface. */
  readonly titleOklch: OkLch;
  /** The raw OKLCH of the lead — the contrast gate recomputes the ratio against the surface. */
  readonly leadOklch: OkLch;
  /** The raw OKLCH of the surface — the background both texts are read against. */
  readonly surfaceOklch: OkLch;
  /** The raw OKLCH of the accent — the contrast gate recomputes the eyebrow/counter ratio. */
  readonly accentOklch: OkLch;
  /** The title font size, px — the `display-large` role (the LARGEST generated display step, §6). */
  readonly titleFontSizePx: number;
  /** The title line height, px — the `display-large` role's generated line height. */
  readonly titleLineHeightPx: number;
  /** The title font family — the `display-large` role family (the seed DISPLAY/serif font). */
  readonly titleFontFamily: string;
  /** The lead font size, px — the `body-large` typography role (the sans helper voice, §6). */
  readonly leadFontSizePx: number;
  /** The lead line height, px — the `body-large` role's generated line height. */
  readonly leadLineHeightPx: number;
  /** The lead font family — the `body-large` role family (the seed TEXT/sans font). */
  readonly leadFontFamily: string;
  /** The eyebrow + counter font size, px — the `caption` role (the smallest mono datum). */
  readonly monoFontSizePx: number;
  /** The eyebrow + counter line height, px — the `caption` role's generated line height. */
  readonly monoLineHeightPx: number;
  /** The eyebrow + counter font family — the CSS generic `monospace` (the data voice, P-D4). */
  readonly monoFontFamily: string;
  /** The content reading measure, px — the `expanded` breakpoint (a real layout measure, not px). */
  readonly measurePx: number;
  /** The vertical rhythm between eyebrow / title / lead / content, px — a spacing-ramp step. */
  readonly gapPx: number;
  /** The page gutter around the focus content, px — a generous ramp step (a focus moment, §5). */
  readonly gutterPx: number;
  /** The progress-bar thickness, px — the tightest ramp step (a THIN bar, §6). */
  readonly barThicknessPx: number;
  /** The progress-bar corner radius, px — the `control` radius (a ramp step, the pill end-cap). */
  readonly barRadiusPx: number;
  /** The progress-fill transition duration, ms — the theme `motion.durations['medium.2']`. */
  readonly transitionMs: number;
  /** The progress-fill easing as a CSS `cubic-bezier(...)` — the theme's `standard` on-screen curve. */
  readonly easing: string;
}

/** The wizard TITLE role — `display-large`, the LARGEST generated display step (doc 17 §6). Falls back
 *  to `display-small` then `headline` so a reshaped seed still lands on a display voice. */
function titleRole(theme: Theme): TypographyRole | undefined {
  return (
    theme.typography.find((r) => r.name === 'display-large') ??
    theme.typography.find((r) => r.name === 'display-small') ??
    theme.typography.find((r) => r.name === 'headline') ??
    theme.typography[0]
  );
}

/** Find a breakpoint's min-width as the content reading measure. `expanded` (840px) is the wizard's
 *  focus measure — wider than EmptyState's `medium` (a question + input needs the room) but still a
 *  generated value. Falls back to `medium` then the first breakpoint so the pick is total. */
function readingMeasurePx(theme: Theme): number {
  const bp =
    theme.breakpoints.find((b) => b.name === 'expanded') ??
    theme.breakpoints.find((b) => b.name === 'medium') ??
    theme.breakpoints[0];
  return bp ? bp.minWidthPx : 840;
}

/** The theme's `standard` on-screen easing as a CSS `cubic-bezier(...)` (the default move curve, the
 *  same one @eden/theme emits as `--ease-standard`). Falls back to the linear-safe `ease` keyword. */
function standardEasing(theme: Theme): string {
  const curve = theme.motion.easing['standard'];
  return curve ? `cubic-bezier(${curve.join(', ')})` : 'ease';
}

/** The `medium.2` (300ms) duration — the theme's mid on-screen move, the progress-fill transition. */
function transitionMs(theme: Theme): number {
  return theme.motion.durations['medium.2'];
}

/**
 * Derive the full {@link WizardShellTokens} from a generated theme. PURE: the theme is the single
 * input. The title is the `display-large` SERIF role (the largest step, §6), the lead the `body-large`
 * SANS role (§6), the eyebrow/counter the mono voice, the measure the `expanded` breakpoint, the
 * progress transition the theme's `medium.2` + `standard` curve — nothing is re-spelled here.
 */
export function deriveWizardShellTokens(theme: Theme): WizardShellTokens {
  const roles = theme.roles;
  const title = titleRole(theme);
  const lead = proportion(theme, 'body-large');
  const mono = proportion(theme, 'caption');
  const titleFontSizePx = title ? title.fontSizePx : theme.controlGeometry.fontSizePx;
  const titleLineHeightPx = title
    ? Math.round(title.fontSizePx * title.lineHeight)
    : theme.controlGeometry.lineHeightPx;
  return {
    surface: oklchToCss(roles.surface.value),
    title: oklchToCss(roles.onSurface.value),
    lead: oklchToCss(roles.outline.value),
    accent: oklchToCss(roles.primary.value),
    track: oklchToCss(roles.outline.value),
    fill: oklchToCss(roles.primary.value),
    titleOklch: roles.onSurface.value,
    leadOklch: roles.outline.value,
    surfaceOklch: roles.surface.value,
    accentOklch: roles.primary.value,
    titleFontSizePx,
    titleLineHeightPx,
    titleFontFamily: title ? title.fontFamily : 'inherit',
    leadFontSizePx: lead.fontSizePx,
    leadLineHeightPx: lead.lineHeightPx,
    leadFontFamily: lead.fontFamily,
    monoFontSizePx: mono.fontSizePx,
    monoLineHeightPx: mono.lineHeightPx,
    monoFontFamily: MONO_FAMILY,
    measurePx: readingMeasurePx(theme),
    // The eyebrow↔title↔lead↔content rhythm is `space-5` (20px) — a generous focus-moment step (§5:
    // generosity only for focus moments); the page gutter is `space-8` (40px) — the full-screen focus
    // needs air; the progress bar is `space-1` (4px) THIN (§6); its end-cap is the `control` radius.
    gapPx: space(theme, 5),
    gutterPx: space(theme, 8),
    barThicknessPx: space(theme, 1),
    barRadiusPx: radiusPx(theme, 'control'),
    transitionMs: transitionMs(theme),
    easing: standardEasing(theme),
  };
}

/**
 * The progress FRACTION for a step — `index / (count − 1)`, clamped to [0, 1]. The FIRST step reads 0
 * (an empty bar — the journey has not started) and the LAST reads 1 (a full bar — arrival). A
 * single-step wizard reads 1 (there is nowhere to progress). This is the ONE fraction home; the
 * property lane asserts monotonicity + the endpoints + the exact `i/(n−1)` value.
 */
export function wizardProgressFraction(stepIndex: number, stepCount: number): number {
  if (stepCount <= 1) return 1;
  const clampedIndex = Math.max(0, Math.min(stepIndex, stepCount - 1));
  return clampedIndex / (stepCount - 1);
}

/**
 * Render a {@link WizardShellTokens} + the active step's progress fraction as the inline `style`
 * custom-property string the component binds. Cites the shared `styleVars` emitter — the markup
 * references `var(--eden-wizard-shell-*)` only. The fraction is a unitless number (a `scaleX`
 * multiplier), so it is emitted RAW (not px-suffixed) — the one non-px numeric var.
 */
export function wizardShellStyleVars(tokens: WizardShellTokens, progressFraction: number): string {
  const entries: readonly StyleEntry[] = [
    ['surface', tokens.surface],
    ['title', tokens.title],
    ['lead', tokens.lead],
    ['accent', tokens.accent],
    ['track', tokens.track],
    ['fill', tokens.fill],
    ['title-font-size', tokens.titleFontSizePx],
    ['title-line-height', tokens.titleLineHeightPx],
    ['title-font-family', tokens.titleFontFamily],
    ['lead-font-size', tokens.leadFontSizePx],
    ['lead-line-height', tokens.leadLineHeightPx],
    ['lead-font-family', tokens.leadFontFamily],
    ['mono-font-size', tokens.monoFontSizePx],
    ['mono-line-height', tokens.monoLineHeightPx],
    ['mono-font-family', tokens.monoFontFamily],
    ['measure', tokens.measurePx],
    ['gap', tokens.gapPx],
    ['gutter', tokens.gutterPx],
    ['bar-thickness', tokens.barThicknessPx],
    ['bar-radius', tokens.barRadiusPx],
    ['transition', `${String(tokens.transitionMs)}ms`],
    ['easing', tokens.easing],
    // the fraction is a unitless scaleX multiplier — emitted RAW (styleVars only px-suffixes bare
    // numbers), so we pre-format it to a string to bypass the px suffix.
    ['progress', String(progressFraction)],
  ];
  return styleVars(VAR_PREFIX, entries);
}
